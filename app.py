
import streamlit as st
import requests
import openai
import math

st.title("AI-Powered US Job Search for Recruiters")

st.markdown(
    "This app searches all available US job postings by title, filters out recruiter-hostile posts, "
    "and uses GPT to assess whether a company is a staffing/recruiting agency and whether they might welcome recruiter help."
)

# User inputs
job_query = st.text_input("Job Title Keyword (e.g., Project Manager):", value="")
max_results = st.number_input("Max number of jobs to analyze (up to 100)", min_value=1, max_value=100, value=25, step=5)

st.subheader("🔐 API Keys (kept private)")
adzuna_app_id = st.text_input("Adzuna App ID", type="password")
adzuna_app_key = st.text_input("Adzuna App Key", type="password")
openai_api_key = st.text_input("OpenAI API Key (starts with 'sk-')", type="password")

if st.button("Search Jobs"):
    if not job_query or not adzuna_app_id or not adzuna_app_key or not openai_api_key:
        st.error("Please enter all required fields.")
        st.stop()

    all_jobs = []
    num_pages = math.ceil(min(max_results, 100) / 50)
    for page in range(1, num_pages + 1):
        api_url = f"https://api.adzuna.com/v1/api/jobs/us/search/{page}"
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
            all_jobs.extend(data.get("results", []))
        except Exception as e:
            st.error(f"Failed to fetch page {page} from Adzuna: {e}")
            break

    if not all_jobs:
        st.warning("No jobs found.")
        st.stop()

    keyword_words = job_query.lower().split()
    openai_client = openai.OpenAI(api_key=openai_api_key)

    filtered_jobs = []
    for job in all_jobs:
        title = job.get("title", "")
        company = job.get("company", {}).get("display_name", "N/A")
        desc = job.get("description", "") or ""
        url = job.get("redirect_url", "#")
        text = f"{title} {desc}".lower()

        # Filter out posts explicitly rejecting recruiters
        if any(term in text for term in ["no recruiters", "no agencies", "no recruitment agencies"]):
            continue
        if not any(word in title.lower() for word in keyword_words):
            continue

        # Use GPT to determine if the company is likely a staffing/recruiting agency
        agency_check_prompt = (
            f"Is '{company}' a staffing or recruiting agency? "
            "Answer 'Yes' or 'No'. Do not explain."
        )
        try:
            agency_check_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": agency_check_prompt}],
                max_tokens=5,
                temperature=0
            )
            agency_answer = agency_check_response.choices[0].message.content.strip().lower()
        except Exception as e:
            agency_answer = "error"
            continue

        if "yes" in agency_answer:
            continue  # exclude agency listings

        # If passed, keep for recruiter-fit GPT evaluation
        filtered_jobs.append({
            "title": title,
            "company": company,
            "description": desc,
            "url": url
        })
        if len(filtered_jobs) >= max_results:
            break

    if not filtered_jobs:
        st.warning("No suitable jobs found after AI agency check.")
        st.stop()

    results = []
    for job in filtered_jobs:
        fit_prompt = (
            "You are an AI assistant helping a recruiter. Determine if the following job post "
            "suggests the company might be open to working with external recruiters. "
            "Keep your response to one or two sentences.\n"
            f"<<<{job['description']}>>>"
        )
        try:
            fit_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": fit_prompt}],
                max_tokens=100,
                temperature=0
            )
            analysis = fit_response.choices[0].message.content.strip()
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
