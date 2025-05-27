
import streamlit as st
import requests
import openai
import math

st.title("🛠 Debug Mode: AI-Powered US Job Search for Recruiters")

st.markdown(
    "This debug version shows **why** each job was excluded during filtering and GPT analysis. "
    "Use it to fine-tune your search or confirm GPT isn't over-filtering."
)

# User inputs
job_query = st.text_input("Job Title Keyword (e.g., Project Manager):", value="project manager")
max_results = st.number_input("Max number of jobs to analyze (up to 100)", min_value=10, max_value=100, value=20, step=10)
page_size = st.number_input("Jobs per page", min_value=5, max_value=25, value=10, step=5)
page_number = st.number_input("Page number to view", min_value=1, value=1, step=1)

# Toggles
enable_gpt_agency_check = st.checkbox("Enable GPT agency exclusion", value=True)
enable_gpt_recruiter_check = st.checkbox("Enable GPT recruiter-fit analysis", value=True)

st.subheader("🔐 API Keys")
adzuna_app_id = st.text_input("Adzuna App ID", type="password")
adzuna_app_key = st.text_input("Adzuna App Key", type="password")
openai_api_key = st.text_input("OpenAI API Key (starts with 'sk-')", type="password")

if st.button("Search Jobs"):
    if not job_query or not adzuna_app_id or not adzuna_app_key or not openai_api_key:
        st.error("Please enter all required fields.")
        st.stop()

    openai_client = openai.OpenAI(api_key=openai_api_key)
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
            st.error(f"Failed to fetch page {page}: {e}")
            break

    keyword_words = job_query.lower().split()
    fallback_terms = ["staffing", "recruiting", "recruitment", "talent", "consulting", "agency"]
    filtered_results = []
    exclusions_log = []

    for job in all_jobs:
        try:
            title = job.get("title", "")
            company = job.get("company", {}).get("display_name", "N/A")
            desc = job.get("description", "") or ""
            url = job.get("redirect_url", "#")
            text = f"{title} {desc}".lower()

            if any(term in text for term in ["no recruiters", "no agencies", "no recruitment agencies"]):
                exclusions_log.append((company, title, "contains 'no recruiters' language"))
                continue
            if not any(word in title.lower() for word in keyword_words):
                exclusions_log.append((company, title, "title does not match keyword"))
                continue

            # GPT agency check
            if enable_gpt_agency_check:
                agency_answer = "unknown"
                try:
                    agency_check_prompt = (
                        f"You are a business classifier. Only respond with 'Yes' or 'No'. "
                        f"Is the company '{company}' a staffing or recruiting agency?"
                    )
                    agency_response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": agency_check_prompt}],
                        max_tokens=5,
                        temperature=0
                    )
                    agency_answer = agency_response.choices[0].message.content.strip().lower()
                except:
                    agency_answer = "error"

                if agency_answer == "yes":
                    exclusions_log.append((company, title, "GPT says 'yes' to agency"))
                    continue
                if agency_answer not in ["yes", "no"] or agency_answer == "error":
                    if any(term in company.lower() for term in fallback_terms):
                        exclusions_log.append((company, title, "fallback: company name matched agency keyword"))
                        continue

            # Recruiter-fit analysis
            analysis = "GPT recruiter-fit check skipped"
            if enable_gpt_recruiter_check:
                try:
                    fit_prompt = (
                        "You are an AI assistant helping a recruiter. Determine if the following job post "
                        "suggests the company might be open to working with external recruiters. "
                        "Keep your response to one or two sentences.\n"
                        f"<<<{desc}>>>"
                    )
                    fit_response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": fit_prompt}],
                        max_tokens=100,
                        temperature=0
                    )
                    analysis = fit_response.choices[0].message.content.strip()
                except Exception as e:
                    analysis = f"GPT error: {e}"

            filtered_results.append({
                "Company": company,
                "Job Title": title,
                "Link": f"[Open Posting]({url})",
                "AI Analysis": analysis
            })

            if len(filtered_results) >= max_results:
                break
        except Exception as e:
            exclusions_log.append(("Unknown", "Unknown", f"job parsing error: {e}"))
            continue

    if not filtered_results:
        st.warning("No jobs passed the filters.")
        if exclusions_log:
            st.subheader("🧾 Exclusion Reasons")
            for company, title, reason in exclusions_log[:30]:
                st.text(f"- {company} | {title} | Reason: {reason}")
        st.stop()

    total_pages = math.ceil(len(filtered_results) / page_size)
    if page_number > total_pages:
        st.warning(f"Only {total_pages} page(s) available.")
        st.stop()

    start = (page_number - 1) * page_size
    end = start + page_size
    display = filtered_results[start:end]

    st.markdown(f"### Showing results {start+1}–{min(end, len(filtered_results))} of {len(filtered_results)}")
    header = "| Company | Job Title | Posting Link | AI Analysis |\n|---|---|---|---|"
    rows = [f"| {r['Company']} | {r['Job Title']} | {r['Link']} | {r['AI Analysis']} |" for r in display]
    st.markdown(header + "\n" + "\n".join(rows), unsafe_allow_html=True)

    if exclusions_log:
        st.subheader("🧾 Jobs Excluded and Why (First 30)")
        for company, title, reason in exclusions_log[:30]:
            st.text(f"- {company} | {title} | Reason: {reason}")
