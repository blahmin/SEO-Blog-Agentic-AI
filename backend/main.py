from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import gpt_blog_maker as blog
import requests
import base64
import os
import tempfile

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from GPT Blog Maker API!"}

class IdeaRequest(BaseModel):
    genre: str

class IdeaResponse(BaseModel):
    ideas: List[str]

class SelectIdeaRequest(BaseModel):
    ideas: List[str]

class SelectedIdeaResponse(BaseModel):
    selected_idea: str

class OutlineRequest(BaseModel):
    idea: str
    length_type: str

class OutlineResponse(BaseModel):
    outline: str

class WriterRequest(BaseModel):
    outline: str
    writing_style: Optional[str] = "Professional, engaging, and informative"
    length_type: str

class WriterResponse(BaseModel):
    blog_post: str

class PublishRequest(BaseModel):
    title: str
    content: str
    status: str  
    featured_image_url: Optional[str] = None
    photographer_name: Optional[str] = None
    photographer_link: Optional[str] = None


@app.post("/generate_ideas", response_model=IdeaResponse)
def generate_ideas(req: IdeaRequest):
    """Generate 3 SEO-optimized blog ideas based on the given genre."""
    try:
        ideas_text = blog.seo_gpt(task="ideas", genre=req.genre)
        return {"ideas": [ideas_text]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/select_idea", response_model=SelectedIdeaResponse)
def select_idea(req: SelectIdeaRequest):
    """Use GPT to pick the 'best' idea."""
    try:
        best_idea = blog.reviewer_gpt(req.ideas)
        return {"selected_idea": best_idea}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/generate_outline", response_model=OutlineResponse)
def generate_outline(req: OutlineRequest):
    """Generate an SEO-optimized outline for a selected idea & length_type."""
    try:
        outline = blog.outline_gpt(req.idea, req.length_type)
        return {"outline": outline}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/generate_blog", response_model=WriterResponse)
def generate_blog(req: WriterRequest):
    """Generate the full blog post from the outline, style, and length."""
    try:
        blog_post = blog.writer_gpt(
            outline=req.outline,
            writing_style=req.writing_style,
            length_type=req.length_type
        )
        return {"blog_post": blog_post}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/get_random_image")
def get_random_image(genre: str = Query(...)):
    """
    Returns a random Unsplash photo for the given genre (orientation=landscape),
    so the front-end can preview it before publishing.
    """
    UNSPLASH_ACCESS_KEY = blog.UNSPLASH_ACCESS_KEY
    url = (
        f"https://api.unsplash.com/photos/random"
        f"?query={genre}"
        f"&orientation=landscape"
        f"&client_id={UNSPLASH_ACCESS_KEY}"
    )
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        image_url = data["urls"]["full"]
        photographer_name = data["user"]["name"]
        photographer_link = data["user"]["links"]["html"]
        return {
            "image_url": image_url,
            "photographer_name": photographer_name,
            "photographer_link": photographer_link,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching random Unsplash photo: {str(e)}")

@app.post("/publish")
def publish_blog(req: PublishRequest):
    """
    Publish or draft the blog post on WordPress, using the
    featured_image_url (and photographer info) the client already fetched.
    """
    try:
        WP_URL = blog.WP_URL
        WP_USER = blog.WP_USER
        WP_APP_PASSWORD = blog.WP_APP_PASSWORD

        auth_str = f"{WP_USER}:{WP_APP_PASSWORD}"
        auth_bytes = auth_str.encode("utf-8")
        auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/json"
        }

        post_data = {
            "title": req.title,
            "content": req.content,
            "status": req.status
        }
        response = requests.post(WP_URL, json=post_data, headers=headers)
        response.raise_for_status()
        post_json = response.json()
        new_post_id = post_json.get("id")

        featured_image_url = None
        if new_post_id and req.featured_image_url:
            set_wp_featured_image(
                post_id=new_post_id,
                image_url=req.featured_image_url,
                photographer_name=req.photographer_name or "",
                photographer_link=req.photographer_link or "",
            )
            featured_image_url = req.featured_image_url

        return {
            "detail": f"Post successfully {req.status} to WordPress!",
            "postId": new_post_id,
            "featuredImageUrl": featured_image_url
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def set_wp_featured_image(post_id, image_url, photographer_name, photographer_link):
    """
    1. Download image to temp file
    2. Upload to WP (multipart/form-data)
    3. Set as featured, update alt_text, append credit
    """
    WP_API_BASE = "https://YOUR_WEBSITE/wp-json/wp/v2"
    WP_USER = blog.WP_USER
    WP_APP_PASSWORD = blog.WP_APP_PASSWORD

    auth_str = f"{WP_USER}:{WP_APP_PASSWORD}"
    auth_bytes = auth_str.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_base64}"
    }

    temp_file_path = None
    try:
        r = requests.get(image_url, stream=True)
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            temp_file_path = tmp.name
    except Exception as e:
        print("Error downloading Unsplash image:", e)
        return

    media_id = None
    if temp_file_path:
        file_name = os.path.basename(temp_file_path)
        media_endpoint = f"{WP_API_BASE}/media"
        try:
            with open(temp_file_path, "rb") as img_file:
                files = {
                    "file": (file_name, img_file, "image/jpeg")
                }
                upload_resp = requests.post(media_endpoint, headers=headers, files=files)
            upload_resp.raise_for_status()
            media_data = upload_resp.json()
            media_id = media_data.get("id")
        except Exception as e:
            print("Error uploading image to WordPress:", e)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    if media_id:
        media_patch_endpoint = f"{WP_API_BASE}/media/{media_id}"
        alt_text_content = f"{image_url} by {photographer_name}" if photographer_name else image_url
        try:
            patch_alt_resp = requests.post(
                media_patch_endpoint,
                headers={**headers, "Content-Type": "application/json"},
                json={"alt_text": alt_text_content}
            )
            patch_alt_resp.raise_for_status()
        except Exception as e:
            print("Error setting alt text on media:", e)

    if media_id:
        post_endpoint = f"{WP_API_BASE}/posts/{post_id}"
        try:
            update_resp = requests.post(
                post_endpoint,
                headers={**headers, "Content-Type": "application/json"},
                json={"featured_media": media_id}
            )
            update_resp.raise_for_status()
            updated_post = update_resp.json()
        except Exception as e:
            print("Error setting featured media:", e)
            return

        try:
            existing_content = updated_post.get("content", {}).get("rendered", "")
            credit_html = (
                f'<p style="font-size:small;">Photo by '
                f'<a href="{photographer_link}" target="_blank" rel="noopener">'
                f'{photographer_name}</a> on '
                f'<a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>.</p>'
            )
            new_content = existing_content + credit_html
            patch_resp = requests.post(
                post_endpoint,
                headers={**headers, "Content-Type": "application/json"},
                json={"content": new_content}
            )
            patch_resp.raise_for_status()
        except Exception as e:
            print("Error adding credit to post:", e)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
