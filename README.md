# Agentic AI solution for SEO blogs. 
Automates the blogging process, from generating the article, reviewing the article, publishing it to wordpress, and even finding relevant images for the blog.

## Features
-Creates blogs from an inputted genre with AI
-Can specify the length of the blog- short, medium, long
-Can upload and publish directly to wordpress site
-Gathers relevant images to the genre from Unspash, and properly credits the photographer

### Requirements
-GPT API Key
-Wordpress site, requires you to input the site link as well as the login info. 
-Unspash API key (need to register dev account, it is free)

### How to run
Install all dependencies (fastapi pydantic requests uvicorn openai)
Fill out all the fields in gpt_blog_maker and main for api's and website urls
Run main.py
open seperate terminal and run 'cd frontend'
in the frontend terminal, run 'npm start' 
it should open a new browser with the tool
