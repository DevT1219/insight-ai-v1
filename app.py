import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# 1. PAGE CONFIG (Must be at the very top)
st.set_page_config(page_title="InsightAI V1", layout="wide")

st.title("🛡️ InsightAI: Sales Integrity & Performance")

# 2. SIDEBAR - The only place to upload
st.sidebar.header("Data Control Center")
uploaded_file = st.sidebar.file_uploader("Upload CRM Export (CSV)", type="csv")

# 3. THE GATE - Only run if a file is uploaded
if uploaded_file is not None:
    try:
        # --- LOAD & CLEAN ---
        df_raw = pd.read_csv(uploaded_file)
        df = df_raw.copy()
        # Clean column names (Colab Logic)
        df.columns = (df.columns.str.lower().str.replace(" ", "_").str.replace("(", "").str.replace(")", ""))
        
        # --- PREP DATA (Colab Logic) ---
        df["followupdate"] = pd.to_datetime(df["followupdate"], errors="coerce")
        df["login_date"] = pd.to_datetime(df.get("login_date"), errors="coerce")
        today = pd.Timestamp.today()
        
        stage_map = {
            "Lead Assigned": "Qualified", "Lead Qualified": "Qualified",
            "App not started": "APNS", "App Start": "App Start",
            "Ready to Share": "RTS", "Bank Prospect": "Bank Prospect",
            "Login": "Login", "PF Paid": "Login", "Sanction": "Login", "Disbursed": "Login",
            "Lost": "Lost", "Disqualified": "Lost", "Future Prospect": "Lost"
        }
        df["funnel_stage"] = df["prospectstage"].map(stage_map)
        df.loc[df["login_date"].notna(), "funnel_stage"] = "Login"

        stage_order = {"Qualified": 1, "APNS": 2, "App Start": 3, "RTS": 4, "Bank Prospect": 5, "Login": 6}
        
        def get_max_stage(row):
            dates = [("Login", "login_date"), ("Bank Prospect", "bank_prospect_date"), 
                     ("RTS", "rts_date"), ("App Start", "app_start_date"), 
                     ("APNS", "app_not_started_date"), ("Qualified", "qualified_date")]
            for stage, col in dates:
                if col in row.index and pd.notna(row[col]): return stage
            return "Qualified"

        df["max_stage"] = df.apply(get_max_stage, axis=1)
        df["stage_rank"] = df["max_stage"].map(stage_order)
        df["converted"] = (df["max_stage"] == "Login").astype(int)

        # --- CALCULATE FUNNEL ---
        funnel_order = ["Qualified", "APNS", "App Start", "RTS", "Bank Prospect", "Login"]
        funnel_cumulative = [df[df["stage_rank"] >= stage_order[s]].shape[0] for s in funnel_order]
        funnel_df = pd.DataFrame({"stage": funnel_order, "leads": funnel_cumulative})
        funnel_df["next_stage_leads"] = funnel_df["leads"].shift(-1)
        funnel_df["drop_percent"] = ((funnel_df["leads"] - funnel_df["next_stage_leads"]) / funnel_df["leads"]) * 100

        # --- UI DISPLAY: FUNNEL ---
        st.header("📊 Funnel & Drop-off Analysis")
        col1, col2 = st.columns([1, 2])
        with col1:
            worst_drop = funnel_df.dropna().sort_values("drop_percent", ascending=False).iloc[0]
            st.metric("Critical Drop Stage", worst_drop['stage'], f"{worst_drop['drop_percent']:.1f}% Drop")
        with col2:
            st.bar_chart(funnel_df.set_index("stage")["leads"])

        # --- GLOBAL LIFT INSIGHTS ---
        st.divider()
        st.header("🌍 Growth Driver (Lift Analysis)")
        features = ["nf_task_fin", "nf_type_fin", "owneridname", "srt_bucket"]
        insights = []
        for col in features:
            if col in df.columns:
                stats = df.groupby(col)["converted"].agg(["mean","count"])
                stats = stats[stats["count"] > 20].sort_values("mean", ascending=False)
                if len(stats) >= 2:
                    lift = stats.iloc[0]["mean"] / max(stats.iloc[-1]["mean"], 0.0001)
                    insights.append({"feature": col, "best": stats.index[0], "worst": stats.index[-1], "lift": lift})
        
        if insights:
            top_i = sorted(insights, key=lambda x: x['lift'], reverse=True)[0]
            st.success(f"**Insight:** {top_i['feature'].upper()} is your top lever. **{top_i['best']}** converts **{top_i['lift']:.2f}x** better than {top_i['worst']}.")

        # --- INTEGRITY AUDIT ---
        st.divider()
        st.header("🛡️ Compliance Audit (Top 5 RMs)")
        
        integrity_checks = [
            ("Lost without 3 attempts", (df["reason"].str.contains("connect", case=False, na=False)) & (df["funnel_stage"] == "Lost") & (df.get("calls_after_latest_stage", 0).fillna(0) < 3)),
            ("CRM calls without Jerry record", (df["calldatebucket"].notna()) & (df["last_call_jerry"].isna())),
            ("Missed followups", (df["followupdate"].notna()) & (df["followupdate"] < today) & (df.get("calls_after_followup_date", 0).fillna(0) == 0))
        ]

        grid = st.columns(2)
        for i, (title, condition) in enumerate(integrity_checks):
            with grid[i % 2]:
                st.subheader(f"📍 {title}")
                counts = df[condition].groupby("owneridname").size().reset_index(name='Violations').sort_values("Violations", ascending=False).head(5)
                if not counts.empty:
                    chart = alt.Chart(counts).mark_bar(color='#4F46E5').encode(
                        x=alt.X('owneridname:N', sort='-y', title="RM Name"),
                        y='Violations:Q'
                    ).properties(height=250)
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.success("100% Compliance")

    except Exception as e:
        st.error(f"🔥 Error: {e}")
        st.info("Check your CSV columns. Need: prospectstage, owneridname, and date columns.")

else:
    # This is what shows up when the app launches (No Error!)
    st.info("👋 Welcome Founder. Please upload your CRM CSV in the sidebar to generate the V1 Audit.")
    st.markdown("""
    ### V1 Audit Capabilities:
    * **Funnel Mapping:** Automatically calculates drop-offs between stages.
    * **Lift Analysis:** Identifies which RM or Task Type drives the most conversions.
    * **Integrity Check:** Flags process violations (Lost leads, Missed followups).
    """)
