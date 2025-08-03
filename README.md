# AI Powered Research Assistant

Description: Agent takes a research topic, fetches academic papers, summarizes key findings, and organizes notes in folders.

This project was created as a helper tool to ease quick research tasks that may require researching introductory papers, and web articles for a basic foundation.

This Project ultimately uses LLMs like ChatGPT to summarise and create queries regarding Scientefic literature and web queries. Other models can be used too.

## Tools Used

Multiple different python libraries are used in this project to ease the process of collecting data. All of them are available through pip.

Gradio is used to create the WebUI/Frontend. OpenAI library is used to query OpenAI models, Web is searched via duckduckgo-search (DDGS) and Scientefic papers are searched via the arXiv.org API.
 
After getting links to various relevant websites, they are web scraped by the use of BeautifulSoup library.

Finally all the summaries are stored in markdown files in their resepective folders.

A Zip file is created to share for more portablity, available for download from the frontend.

Components requeried to setup:
- OpenAI API Key: api_key variable must be set in the script.
- Search Results: You can modify the MAX_WEB_RESULTS and MAX_PAPER_RESULTS constants at the top of the script to control how many sources are fetched.

## Running The Project

This Project is meant to be portable and requires minimal setup.

```bash
# Clone the Repo
git clone <your-repository-url>
cd <repository-directory>

# Setup the python environent
python3 -m venv .venv
pip install -r requirements.txt

# Running the main file
python3 main.py
```