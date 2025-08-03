import gradio as gr
import openai
import os
import re
import requests
import json
from bs4 import BeautifulSoup
from ddgs import DDGS
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import shutil

api_key =" Your API KEY"

try:
    client = openai.OpenAI(api_key=api_key)
except openai.OpenAIError as e:
    print("OpenAI API key is invalid or not found. Please check the hardcoded key.")
    client = None

RESEARCH_DIR = Path("research_projects")
MAX_WEB_RESULTS = 5
MAX_PAPER_RESULTS = 5

def sanitize_filename(name):
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    sanitized = sanitized.replace(" ", "_")
    return sanitized[:100]

def create_folders(topic):
    base_path = RESEARCH_DIR / sanitize_filename(topic)
    web_path = base_path / "Web_Articles"
    papers_path = base_path / "Academic_Papers"
    
    base_path.mkdir(parents=True, exist_ok=True)
    web_path.mkdir(exist_ok=True)
    papers_path.mkdir(exist_ok=True)
    
    return base_path, web_path, papers_path

def zip_research_folder(folder_path):
    folder_path = Path(folder_path)
    output_filename = folder_path.parent / folder_path.name
    zip_filepath = shutil.make_archive(str(output_filename), 'zip', str(folder_path))
    print(f"Created zip file at: {zip_filepath}")
    return zip_filepath

def get_search_queries(topic):
    prompt = f"""
    Given the research topic "{topic}", generate a list of 3 effective web search queries 
    and 2 academic search queries.
    Format the output as a valid JSON object string with two keys: "web_queries" and "academic_queries".
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a helpful research assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error generating search queries with AI: {e}")
        return {
            "web_queries": [f"introduction to {topic}", f"{topic} applications"],
            "academic_queries": [f"{topic} review paper", f"breakthroughs in {topic}"]
        }

def search_web(queries):
    urls = set()
    try:
        with DDGS() as ddgs:
            for query in queries:
                print(f"Searching web for: '{query}'")
                results = list(ddgs.text(query, max_results=MAX_WEB_RESULTS))
                for r in results:
                    if 'href' in r:
                        urls.add(r['href'])
    except Exception as e:
        print(f"An error occurred during web search: {e}")
    return list(urls)

def search_papers(queries):
    papers = []
    for query in queries:
        try:
            print(f"Searching arXiv for: '{query}'")
            base_url = 'http://export.arxiv.org/api/query?'
            search_query = f'all:{urllib.parse.quote_plus(query)}'
            query_url = f'{base_url}search_query={search_query}&sortBy=relevance&max_results={MAX_PAPER_RESULTS}'
            
            with urllib.request.urlopen(query_url, timeout=15) as url_response:
                root = ET.fromstring(url_response.read())
            
            atom_ns = '{http://www.w3.org/2005/Atom}'
            for entry in root.findall(f'{atom_ns}entry'):
                papers.append({
                    "title": entry.find(f'{atom_ns}title').text.strip(),
                    "abstract": entry.find(f'{atom_ns}summary').text.strip().replace('\n', ' '),
                    "url": entry.find(f'{atom_ns}link').attrib['href']
                })
        except Exception as e:
            print(f"Could not fetch papers from arXiv for query '{query}': {e}")
    return papers

def scrape_website_content(url):
    print(f"Scraping: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        return soup.get_text(separator='\n', strip=True)[:12000]
    except requests.RequestException as e:
        print(f"Error scraping {url}: {e}")
        return None

def summarize_text(text, topic, source_type="text"):
    if not text: return "Could not summarize: No content provided."
    print(f"Summarizing {source_type}...")
    prompt = f"""Please summarize the following {source_type} in the context of "{topic}". Extract key points and findings. Present the summary in well-structured markdown. Text: --- {text} ---"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a world-class research summarizer providing clear, concise summaries in markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during summarization: {e}")
        return f"Could not summarize text due to an API error: {e}"

def research_topic(topic, progress=gr.Progress(track_tqdm=True)):
    if not client:
        error_message = "## Configuration Error\n\nOpenAI API key is not valid. Please check the hardcoded key in the script and restart."
        return (error_message, False, False, "", "", None)

    progress(0, desc="Starting Research...")
    base_path, web_path, papers_path = create_folders(topic)
    
    progress(0.1, desc="Generating search queries...")
    queries = get_search_queries(topic)
    progress(0.2, desc="Searching the web...")
    web_urls = search_web(queries.get("web_queries", [topic]))
    progress(0.3, desc="Searching academic papers...")
    papers = search_papers(queries.get("academic_queries", [topic]))
    
    web_summaries_md = ""
    paper_summaries_md = ""

    total_web_articles = len(web_urls)
    if total_web_articles > 0:
        for i, url in enumerate(web_urls):
            progress(0.4 + (i / total_web_articles) * 0.3, desc=f"Processing Web Article {i+1}/{total_web_articles}...")
            content = scrape_website_content(url)
            if content:
                summary = summarize_text(content, topic, source_type="web article")
                filename = sanitize_filename(url.split('/')[-1] or url.split('/')[-2]) + ".md"
                with open(web_path / filename, "w", encoding="utf-8") as f:
                    f.write(f"# Summary for: {url}\n\n---\n\n{summary}")
                web_summaries_md += f"### Summary for: [{url}]({url})\n---\n{summary}\n\n"

    total_papers = len(papers)
    if total_papers > 0:
        for i, paper in enumerate(papers):
            progress(0.7 + (i / total_papers) * 0.25, desc=f"Processing Paper {i+1}/{total_papers}...")
            summary = summarize_text(paper.get('abstract', ''), topic, source_type="academic paper abstract")
            filename = sanitize_filename(paper.get('title', 'untitled')) + ".md"
            with open(papers_path / filename, "w", encoding="utf-8") as f:
                f.write(f"# {paper.get('title', 'No Title')}\n\n**Source URL:** <{paper.get('url', 'N/A')}>\n\n---\n\n## Summary of Abstract\n\n{summary}")
            paper_summaries_md += f"### {paper.get('title', 'No Title')}\n**Source:** [{paper.get('url', 'N/A')}]({paper.get('url', 'N/A')})\n---\n**Summary of Abstract:**\n{summary}\n\n"

    progress(1, desc="Zipping Project...")
    zip_filepath = zip_research_folder(base_path)
    
    final_message = f"## Research Complete!\n\nYour notes have been saved to `{os.path.abspath(base_path)}` and are summarized below. You can download the complete project as a zip file."
    
    web_accordion_visible = bool(web_summaries_md)
    paper_accordion_visible = bool(paper_summaries_md)
    
    return (final_message, web_accordion_visible, paper_accordion_visible, web_summaries_md, paper_summaries_md, zip_filepath)

css = """
#title { 
    text-align: center; 
    font-family: 'Helvetica Neue', 'Arial', sans-serif; 
    font-weight: 300; 
    font-size: 2.8rem; 
    margin-top: 1rem;
}
#subtitle { 
    text-align: center; 
    color: #555; 
    font-size: 1.2rem; 
    margin-bottom: 2rem; 
}
.gradio-container { 
    max-width: 900px !important; 
    margin: auto !important; 
    padding: 1rem !important; 
}
#input_container {
    padding: 1.5rem;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
}
#start_button {
    width: 100%;
    font-size: 1.1rem !important;
    padding: 0.75rem !important;
    height: auto !important;
}
#output_col {
    margin-top: 2rem;
}
@media (max-width: 768px) {
    #title {
        font-size: 2rem;
    }
    #subtitle {
        font-size: 1rem;
    }
    .gradio-container {
        padding: 0.5rem !important;
    }
    #input_container {
        padding: 1rem;
    }
}
"""

with gr.Blocks(theme=gr.themes.Soft(primary_hue=gr.themes.colors.blue, secondary_hue=gr.themes.colors.sky), css=css) as app:
    gr.Markdown("# AI-Powered Research Assistant", elem_id="title")
    gr.Markdown("Enter a topic below. The assistant will search the web and academic papers, summarize the content, and present the findings for you to review and download.", elem_id="subtitle")

    with gr.Column(elem_id="input_container"):
        topic_input = gr.Textbox(
            label="Research Topic",
            placeholder="e.g., The Impact of Quantum Computing on Modern Cryptography",
            autofocus=True
        )
        start_button = gr.Button("Start Research", variant="primary", elem_id="start_button")

    with gr.Column(visible=False, elem_id="output_col") as output_col:
        status_update = gr.Markdown()
        download_zip = gr.File(label="Download Zipped Research Project", visible=False, interactive=False)
        with gr.Accordion("Web Article Summaries", open=False, visible=False) as web_accordion:
            web_results = gr.Markdown()
        with gr.Accordion("Academic Paper Summaries", open=False, visible=False) as paper_accordion:
            paper_results = gr.Markdown()
    
    def run_research_and_update_ui(topic, progress=gr.Progress(track_tqdm=True)):
        yield (
            gr.update(visible=True),
            gr.update(value="Starting research... Please wait."),
            gr.update(visible=False),
            gr.update(visible=False),
            "",
            "",
            gr.update(visible=False, value=None)
        )
        
        final_message, web_visible, paper_visible, web_md, paper_md, zip_path = research_topic(topic, progress)
        
        yield (
            gr.update(visible=True),
            gr.update(value=final_message),
            gr.update(visible=web_visible),
            gr.update(visible=paper_visible),
            web_md,
            paper_md,
            gr.update(visible=True, value=zip_path)
        )

    start_button.click(
        fn=run_research_and_update_ui,
        inputs=topic_input,
        outputs=[output_col, status_update, web_accordion, paper_accordion, web_results, paper_results, download_zip]
    )

if __name__ == "__main__":
    app.launch()
