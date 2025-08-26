import os, pandas as pd, streamlit as st
from emailer import send_email
from db import (
    init_db, upsert_student_profile, list_jobs, apply_job,
    list_applications_for_student, create_job, list_all_applications,
    set_application_status, get_recruiter_email_by_recruiter_id
)
from auth import signup_flow, login_flow, otp_verify_flow, forgot_password_flow, logout_button

BRAND_NAME = os.getenv("BRAND_NAME", "Campus Placement Portal")
LOGO_PATH = os.path.join("assets", "brand-logo.svg")

st.set_page_config(page_title=BRAND_NAME, page_icon="🎓", layout="wide")
init_db()

st.markdown("""
<style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    .badge {padding: .15rem .5rem; border-radius: .5rem; font-size: .8rem;}
    .badge-applied{background:#DBEAFE; color:#1E3A8A;}
    .badge-shortlisted{background:#FEF3C7; color:#92400E;}
    .badge-interview{background:#E0E7FF; color:#3730A3;}
    .badge-selected{background:#DCFCE7; color:#065F46;}
    .badge-rejected{background:#FEE2E2; color:#991B1B;}
    .brandbar {display:flex; align-items:center; gap:.75rem; padding:.75rem 1rem; border-radius:16px; background:linear-gradient(90deg,#0F172A,#1E3A8A); color:white;}
    .brandbar h1 {font-size:1.25rem; margin:0;}
</style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1,5])
with col_logo:
    try:
        st.image(LOGO_PATH, width=56)
    except Exception:
        st.write("🎓")
with col_title:
    st.markdown(f'<div class="brandbar"><h1>{BRAND_NAME}</h1></div>', unsafe_allow_html=True)

role = st.sidebar.selectbox("Role", ["STUDENT","RECRUITER","ADMIN"], index=0)
st.sidebar.caption("Select a role to view its dashboard")

tabs = st.tabs(["Sign Up","Login","OTP Verify","Forgot Password","Dashboard"])

with tabs[0]:
    signup_flow(role)

with tabs[1]:
    login_flow()

with tabs[2]:
    otp_verify_flow()

with tabs[3]:
    forgot_password_flow()

with tabs[4]:
    auth = st.session_state.get("auth")
    if not auth or auth.get("role") != role:
        st.warning(f"Login as {role.title()} to access the dashboard.")
    else:
        logout_button()
        # STUDENT DASHBOARD
        if role == "STUDENT":
            st.header("Student Dashboard")
            with st.form("profile_form"):
                name = st.text_input("Full Name")
                usn = st.text_input("USN")
                branch = st.text_input("Branch")
                email = st.text_input("Email")
                phone = st.text_input("Phone (10 digits)")
                resume_file = st.file_uploader("Upload Resume (PDF/DOCX)", type=["pdf","docx"])
                saved = st.form_submit_button("Save/Update Profile")
            if saved:
                resume_bytes = resume_file.read() if resume_file else None
                upsert_student_profile(auth["user_id"], name, usn, branch, email, phone, resume_bytes)
                st.success("Profile updated.")

            st.subheader("Available Jobs")
            q = st.text_input("Search jobs (company / role / location)")
            jobs = list_jobs(q=q)
            if jobs:
                df = pd.DataFrame(jobs, columns=["Job ID","Company","Role","Salary","Location","Poster User ID"])
                st.dataframe(df.drop(columns=["Poster User ID"]), use_container_width=True)
                sel = st.number_input("Enter Job ID to apply", min_value=0, step=1)
                if st.button("Apply"):
                    try:
                        ok, student_email = apply_job(auth["user_id"], int(sel))
                        if ok:
                            recruiter_email = get_recruiter_email_by_recruiter_id(int(sel))
                            if student_email:
                                send_email(student_email, "Application Submitted",
                                           f"You have applied to Job ID {int(sel)}.")
                            if recruiter_email:
                                send_email(recruiter_email, "New Applicant",
                                           "A student has applied to your job posting.")
                            st.success("Applied successfully! (Notifications sent if email configured)")
                        else:
                            st.info("You already applied.")
                    except Exception as e:
                        st.error(str(e))
            else:
                st.info("No jobs yet.")

            st.subheader("My Applications")
            apps = list_applications_for_student(auth["user_id"])
            if apps:
                df = pd.DataFrame(apps, columns=["App ID","Company","Role","Status","Applied At","Job ID"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No applications yet.")

        # RECRUITER DASHBOARD
        elif role == "RECRUITER":
            st.header("Recruiter Dashboard")
            with st.form("post_job"):
                company = st.text_input("Company Name")
                role_txt = st.text_area("Role / Job Description")
                salary = st.text_input("Salary (e.g., 8 LPA)")
                location = st.text_input("Location")
                post = st.form_submit_button("Post Job")
            if post:
                if not company or not role_txt:
                    st.error("Company and Role/Description are required")
                else:
                    create_job(auth["user_id"], company.strip(), role_txt.strip(), salary.strip(), location.strip())
                    st.success("Job posted!")

            st.subheader("Applications (All)")
            apps = list_all_applications()
            if apps:
                df = pd.DataFrame(apps, columns=["App ID","Student Name","USN","Company","Role","Status","Applied At","Student ID","Job ID"])
                st.dataframe(df, use_container_width=True)
                app_id = st.number_input("Select Application ID", min_value=0, step=1)
                new_status = st.selectbox("Update Status",
                                          ["Applied","Shortlisted","Interview Scheduled","Selected","Rejected"])
                if st.button("Update Application Status"):
                    student_email, company = set_application_status(int(app_id), new_status)
                    if student_email:
                        send_email(student_email, "Application Status Updated",
                                   f"Your application at {company} is now: {new_status}")
                    st.success("Application status updated.")
            else:
                st.info("No applications yet.")

        # ADMIN DASHBOARD
        else:
            st.header("Admin Dashboard")
            st.info("Admin controls can be expanded (metrics, broadcast emails, user management).")
            apps = list_all_applications()
            if apps:
                df = pd.DataFrame(apps, columns=["App ID","Student Name","USN","Company","Role","Status","Applied At","Student ID","Job ID"])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No applications.")
