
import streamlit as st
import requests
import openai

st.title("AI-Powered US Job Search for Recruiters")

st.markdown(
    "Search all available US job postings by title. "
    "This app filters out posts that mention 'no recruiters' or 'no agencies' and uses GPT to assess recruiter fit."
)

# User inputs
job_query = st.text_input("Job Title Keyword (e.g., Project Manager):", value="")

max_results = st.number_input("Max number of jobs to analyze", min_value=1, max_value=50, value=10, step=1)

st.subheader("🔐 API Keys (kept private)")
adzuna_app_id = st.text_input("Adzuna App ID", type="password")
adzuna_app_key = st.text_input("Adzuna App Key", type="password")
openai_api_key = st.text_input("OpenAI API Key (starts with 'sk-')", type="password")

if st.button("Search Jobs"):
    if not job_query or not adzuna_app_id or not adzuna_app_key or not openai_api_key:
        st.error("Please enter all required fields.")
        st.stop()

    # Build Adzuna API request for US jobs
    api_url = f"https://api.adzuna.com/v1/api/jobs/us/search/1"
    params = {
        "app_id": adzuna_app_id,
        "app_key": adzuna_app_key,
        "results_per_page": 50,
        "what": job_query,
        "content-type": "application/json"
    }

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        st.error(f"Failed to fetch data from Adzuna: {e}")
        st.stop()

    jobs = data.get("results", [])
    if not jobs:
        st.warning("No jobs found.")
        st.stop()

    # Filter and prepare job postings
    keyword_words = job_query.lower().split()
    filtered_jobs = []
    for job in jobs:
        title = job.get("title", "")
        company = job.get("company", {}).get("display_name", "N/A")
        desc = job.get("description", "") or ""
        url = job.get("redirect_url", "#")
        text = f"{title} {desc}".lower()

        if any(word in text for word in ["no recruiters", "no agencies", "no recruitment agencies"]):
            continue
        if not any(word in title.lower() for word in keyword_words):
            continue

        filtered_jobs.append({
            "title": title,
            "company": company,
            "description": desc,
            "url": url
        })

    if not filtered_jobs:
        st.warning("No recruiter-friendly jobs matched your filters.")
        st.stop()

    filtered_jobs = filtered_jobs[:max_results]
    openai_client = openai.OpenAI(api_key=openai_api_key)

    results = []
    for job in filtered_jobs:
        prompt = (
            "You are an AI assistant helping a recruiter. Determine if the following job post "
            "suggests the company might be open to working with external recruiters. "
            "Keep your response to one or two sentences.\n"
            f"<<<{job['description']}>>>"
        )
        try:
            chat_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0
            )
            analysis = chat_response.choices[0].message.content.strip()
        except Exception as e:
            analysis = f"AI error: {e}"

        results.append({
            "Company": job["company"],
            "Job Title": job["title"],
            "Link": f"[Open Posting]({job['url']})",
            "AI Analysis": analysis
        })

    if results:
        st.markdown("### Results")
        header = "| Company | Job Title | Posting Link | AI Analysis |\n|---|---|---|---|"
        rows = [
            f"| {res['Company']} | {res['Job Title']} | {res['Link']} | {res['AI Analysis']} |"
            for res in results
        ]
        table_md = header + "\n" + "\n".join(rows)
        st.markdown(table_md, unsafe_allow_html=True)

        st.caption("Data source: Adzuna US API (adzuna.com)")
