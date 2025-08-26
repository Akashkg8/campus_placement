import re, streamlit as st
from db import (
    create_user, get_user_by_email, check_password, set_password,
    create_otp, verify_otp, mark_email_verified
)
from emailer import send_email

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def signup_flow(role_label: str):
    st.subheader(f"Sign Up — {role_label.title()}")
    with st.form("signup_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        usn = st.text_input("USN (students only)") if role_label.upper()=="STUDENT" else ""
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Create Account")
    if submit:
        if not name.strip():
            st.error("Full Name is required"); return
        if not EMAIL_RE.match(email.strip()):
            st.error("Valid email is required"); return
        if role_label.upper()=="STUDENT" and not usn.strip():
            st.error("USN is required for students"); return
        if len(password) < 8:
            st.error("Password must be at least 8 characters"); return
        try:
            uid = create_user(role_label.upper(), email.strip(), name.strip(), password, usn.strip() or None)
            code = create_otp(uid, "SIGNUP", ttl_seconds=900)
            sent = send_email(email.strip(), "Verify your email (OTP)",
                              f"Your OTP is: {code}\nExpires in 15 minutes.")
            st.session_state["pending_user"] = {
                "user_id": uid, "email": email.strip(), "role": role_label.upper(), "purpose":"SIGNUP"
            }
            st.success("Account created. Check your email for OTP."
                       if sent else "Account created. Email not configured; check server logs for OTP.")
        except Exception as e:
            st.error(str(e))

def login_flow():
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Continue")
    if submit:
        row = get_user_by_email(email.strip())
        if not row:
            st.error("No such user"); return
        uid, role, uemail, name, usn, phash, verified = row
        if not verified:
            st.error("Email not verified. Use Sign Up or OTP verification."); return
        if not check_password(password, phash):
            st.error("Wrong password"); return
        code = create_otp(uid, "LOGIN", ttl_seconds=600)
        sent = send_email(uemail, "Login verification (OTP)",
                          f"Your login OTP is: {code}\nValid for 10 minutes.")
        st.session_state["pending_user"] = {
            "user_id": uid, "email": uemail, "role": role, "purpose":"LOGIN"
        }
        st.info("OTP sent to your email. Enter it on the OTP tab."
                if sent else "Email not configured; check server logs for OTP.")

def forgot_password_flow():
    st.subheader("Forgot Password")
    with st.form("forgot_form"):
        email = st.text_input("Account Email")
        submit = st.form_submit_button("Send Reset OTP")
    if submit:
        row = get_user_by_email(email.strip())
        if not row:
            st.error("No user with that email"); return
        uid, role, uemail, name, usn, phash, verified = row
        code = create_otp(uid, "RESET", ttl_seconds=900)
        sent = send_email(uemail, "Password reset (OTP)",
                          f"Your reset OTP is: {code}\nValid for 15 minutes.")
        st.session_state["pending_user"] = {
            "user_id": uid, "email": uemail, "role": role, "purpose":"RESET"
        }
        st.success("Reset OTP sent." if sent else "Email not configured; check server logs for OTP.")

    st.markdown("---")
    st.subheader("Reset Password (after OTP)")
    with st.form("reset_form"):
        code = st.text_input("Enter OTP")
        newpw = st.text_input("New Password", type="password")
        submit2 = st.form_submit_button("Reset Password")
    if submit2:
        p = st.session_state.get("pending_user")
        if not p or p.get("purpose") != "RESET":
            st.error("Start with 'Forgot Password' to get an OTP."); return
        if not code.strip() or len(newpw) < 8:
            st.error("Valid OTP and password (>=8 chars) required."); return
        if verify_otp(p["user_id"], code.strip(), "RESET"):
            set_password(p["user_id"], newpw)
            st.session_state.pop("pending_user", None)
            st.success("Password updated. You can now login.")
        else:
            st.error("Invalid/expired OTP.")

def otp_verify_flow():
    st.subheader("Verify OTP")
    code = st.text_input("Enter 6-digit OTP")
    if st.button("Verify"):
        p = st.session_state.get("pending_user")
        if not p:
            st.error("No pending OTP action"); return
        if verify_otp(p["user_id"], code, p["purpose"]):
            if p["purpose"] == "SIGNUP":
                mark_email_verified(p["user_id"])
            st.session_state["auth"] = {
                "user_id": p["user_id"], "email": p["email"], "role": p["role"]
            }
            st.session_state.pop("pending_user", None)
            st.success("Verified! You're logged in.")
        else:
            st.error("Invalid or expired OTP.")

def logout_button():
    if st.button("Logout"):
        st.session_state.pop("auth", None)
        st.experimental_rerun()
