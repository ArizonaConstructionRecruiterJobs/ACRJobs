
import streamlit as st
import requests
import openai
import math

st.title("AI-Powered US Job Search for Recruiters")

st.markdown(
    "Search real-time US job postings by title. This tool filters out recruiter-hostile posts, "
    "excludes staffing/recruiting agencies using GPT and fallback keyword checks, and analyzes fit for recruiter outreach."
)

# User inputs
job_query = st.text_input("Job Title Keyword (e.g., Project Manager):", value="")
max_results = st.number_input("Max number of jobs to analyze (up to 100)", min_value=10, max_value=100, value=30, step=10)
page_size = st.number_input("Jobs per page", min_value=5, max_value=25, value=10, step=5)
page_number = st.number_input("Page number to view", min_value=1, value=1, step=1)

st.subheader("🔐 API Keys (kept private and secure)")
adzuna_app_id = st.text_input("Adzuna App ID", type="password")
adzuna_app_key = st.text_input("Adzuna App Key", type="password")
openai_api_key = st.text_input("OpenAI API Key (starts with 'sk-')", type="password")

if st.button("Search Jobs"):
    # Input validation
    if not job_query.strip():
        st.error("Please enter a job title keyword.")
        st.stop()
    if not adzuna_app_id.strip() or not adzuna_app_key.strip():
        st.error("Adzuna credentials are required.")
        st.stop()
    if not openai_api_key.strip() or not openai_api_key.startswith("sk-"):
        st.error("Please enter a valid OpenAI API key.")
        st.stop()

    all_jobs = []
    num_pages = math.ceil(min(max_results, 100) / 50)
    try:
        for page in range(1, num_pages + 1):
            api_url = f"https://api.adzuna.com/v1/api/jobs/us/search/{page}"
            params = {
                "app_id": adzuna_app_id,
                "app_key": adzuna_app_key,
                "results_per_page": 50,
                "what": job_query,
                "content-type": "application/json"
            }

            response = requests.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            all_jobs.extend(data.get("results", []))
    except Exception as e:
        st.error(f"Error retrieving job data: {e}")
        st.stop()

    if not all_jobs:
        st.warning("No jobs found. Try a broader keyword.")
        st.stop()

    keyword_words = job_query.lower().split()
    try:
        openai_client = openai.OpenAI(api_key=openai_api_key)
    except Exception as e:
        st.error(f"Failed to initialize OpenAI: {e}")
        st.stop()

    results = []
    for job in all_jobs:
        try:
            title = job.get("title", "")
            company = job.get("company", {}).get("display_name", "N/A")
            desc = job.get("description", "") or ""
            url = job.get("redirect_url", "#")
            text = f"{title} {desc}".lower()

            if any(term in text for term in ["no recruiters", "no agencies", "no recruitment agencies"]):
                continue
            if not any(word in title.lower() for word in keyword_words):
                continue

            agency_check_prompt = (
                f"You are a business classifier. Only respond with 'Yes' or 'No'. "
                f"Is the company '{company}' a staffing or recruiting agency?"
            )
            agency_answer = "unknown"
            try:
                agency_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": agency_check_prompt}],
                    max_tokens=5,
                    temperature=0
                )
                agency_answer = agency_response.choices[0].message.content.strip().lower()
            except Exception:
                pass

            fallback_terms = ["staffing", "recruiting", "recruitment", "talent", "consulting", "agency"]
            if agency_answer == "yes":
                continue
            if agency_answer not in ["yes", "no"]:
                if any(term in company.lower() for term in fallback_terms):
                    continue

            fit_prompt = (
                "You are an AI assistant helping a recruiter. Determine if the following job post "
                "suggests the company might be open to working with external recruiters. "
                "Keep your response to one or two sentences.\n"
                f"<<<{desc}>>>"
            )
            try:
                fit_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": fit_prompt}],
                    max_tokens=100,
                    temperature=0
                )
                analysis = fit_response.choices[0].message.content.strip()
            except Exception:
                analysis = "AI error during recruiter-fit analysis."

            results.append({
                "Company": company,
                "Job Title": title,
                "Link": f"[Open Posting]({url})",
                "AI Analysis": analysis
            })

            if len(results) >= max_results:
                break
        except Exception:
            continue  # skip any malformed job entry

    if not results:
        st.warning("No suitable jobs found after filtering.")
        st.stop()

    # Pagination after filtering
    total_pages = math.ceil(len(results) / page_size)
    if page_number > total_pages:
        st.warning(f"You selected page {page_number}, but only {total_pages} page(s) of results are available.")
        st.stop()

    start = (page_number - 1) * page_size
    end = start + page_size
    paged_results = results[start:end]

    if paged_results:
        st.markdown(f"### Showing results {start+1}–{min(end, len(results))} of {len(results)}")
        header = "| Company | Job Title | Posting Link | AI Analysis |\n|---|---|---|---|"
        rows = [
            f"| {res['Company']} | {res['Job Title']} | {res['Link']} | {res['AI Analysis']} |"
            for res in paged_results
        ]
        table_md = header + "\n" + "\n".join(rows)
        st.markdown(table_md, unsafe_allow_html=True)
        st.caption("Data source: Adzuna US API (adzuna.com)")
    else:
        st.warning("No results to display on this page.")
