
import streamlit as st
import requests
import openai

st.title("Recruiter-Friendly Job Posting Analyzer")

st.markdown(
    "Enter a job search keyword to find recent job postings. "
    "The app filters out postings that say 'No recruiters' or 'No agencies', "
    "then uses an AI agent to guess how open the company might be to recruiter services."
)

job_query = st.text_input("Job Title Keyword (e.g., Software Engineer):", value="")
max_results = st.number_input("Max number of postings to analyze", min_value=1, max_value=20, value=5, step=1)

if "api_key" not in st.session_state:
    openai_api_key = st.text_input("OpenAI API Key (starts with 'sk-'):", type="password")
    if openai_api_key:
        st.session_state["api_key"] = openai_api_key
else:
    openai_api_key = st.session_state["api_key"]

if st.button("Search Jobs"):
    if not job_query:
        st.error("Please enter search keywords.")
    else:
        api_url = "https://remotive.com/api/remote-jobs"
        params = {"search": job_query, "limit": max_results * 4}
        try:
            response = requests.get(api_url, params=params)
            data = response.json()
        except Exception as e:
            st.error(f"Error fetching job data: {e}")
            st.stop()

        jobs = data.get("jobs", [])
        filtered_jobs = []
        keyword_lower = job_query.lower()
        for job in jobs:
            title = job.get("title", "")
            company = job.get("company_name", "")
            desc = job.get("description", "") or ""
            text = f"{title} {desc}".lower()

            # Exclude jobs with no-recruiter language
            if ("no recruiters" in text) or ("no recruitment agency" in text) or ("no agencies" in text):
                continue

            # Keep only jobs where the job title includes the keyword
            if keyword_lower not in title.lower():
                continue

            filtered_jobs.append(job)

        if not filtered_jobs:
            st.warning("No matching recruiter-friendly jobs found with that title.")
            st.stop()

        filtered_jobs = filtered_jobs[:max_results]

        if not openai_api_key:
            st.error("OpenAI API key required.")
            st.stop()

        client = openai.OpenAI(api_key=openai_api_key)

        results = []
        for job in filtered_jobs:
            title = job.get("title", "N/A")
            company = job.get("company_name", "N/A")
            url = job.get("url")
            description_text = job.get("description", "")

            prompt = (
                "You are an AI assistant helping a recruiter. Determine if the following job post "
                "suggests the company is open to working with external recruiters. "
                "Keep the response to one or two sentences.\n"
                f"<<<{description_text}>>>"
            )

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0
                )
                analysis = response.choices[0].message.content.strip()
            except Exception as e:
                analysis = f"AI error: {e}"

            results.append({
                "Company": company,
                "Job Title": title,
                "Link": f"[Open Posting]({url})",
                "AI Analysis": analysis
            })

        if results:
            st.markdown("**Results:**")
            header = "| Company | Job Title | Posting Link | AI Analysis |\n|---|---|---|---|"
            rows = [
                f"| {res['Company']} | {res['Job Title']} | {res['Link']} | {res['AI Analysis']} |"
                for res in results
            ]
            table_md = header + "\n" + "\n".join(rows)
            st.markdown(table_md, unsafe_allow_html=True)

            st.caption("Data source: Remotive (remotive.com)")
