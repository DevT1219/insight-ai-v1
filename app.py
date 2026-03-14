import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- PAGE SETUP ---
st.set_page_config(page_title="InsightAI | V1 Sales Audit", layout="wide")

st.title("🛡️ InsightAI: B2B Sales Integrity & Performance")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("Data Control Center")
uploaded_file = st.sidebar.file_uploader("Upload CRM CSV", type="csv")

if uploaded_file:
    # 1. LOAD DATA
    df = pd.read_csv(uploaded_file)

    # 2. ANALYTICAL ENGINE (Your Colab Logic)
    def run_full_analysis(df):
        # Cleaning Columns
        df.columns = (df.columns.str.lower().str.replace(" ", "_").str.replace("(", "").str.replace(")", ""))
        
        # Date Conversions
        df["followupdate"] = pd.to_datetime(df["followupdate"], errors="coerce")
        df["login_date"] = pd.to_datetime(df.get("login_date"), errors="coerce")
        today = pd.Timestamp.today()

        # Funnel Mapping
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
        
        # Max Stage Logic
        def get_max_stage(row):
            for stage, rank in sorted(stage_order.items(), key=lambda x: x[1], reverse=True):
                col_name = f"{stage.lower().replace(' ', '_')}_date"
                if col_name in row.index and pd.notna(row[col_name]): return stage
            return "Qualified"
        
        df["max_stage"] = df.apply(get_max_stage, axis=1)
        df["stage_rank"] = df["max_stage"].map(stage_order)
        df["converted"] = (df["max_stage"] == "Login").astype(int)

        # Funnel Cumulative DF
        funnel_order = ["Qualified", "APNS", "App Start", "RTS", "Bank Prospect", "Login"]
        funnel_cumulative = [df[df["stage_rank"] >= stage_order[s]].shape[0] for s in funnel_order]
        funnel_df = pd.DataFrame({"stage": funnel_order, "leads": funnel_cumulative})
        funnel_df["next_stage_leads"] = funnel_df["leads"].shift(-1)
        funnel_df["drop_percent"] = ((funnel_df["leads"] - funnel_df["next_stage_leads"]) / funnel_df["leads"]) * 100

        # Global Insights (Lift)
        features = ["nf_task_fin", "nf_type_fin", "owneridname", "srt_bucket"]
        global_insights = []
        for col in features:
            if col in df.columns:
                stats = df.groupby(col)["converted"].agg(["mean","count"])
                stats = stats[stats["count"] > 20].sort_values("mean", ascending=False)
                if len(stats) >= 2:
                    lift = stats.iloc[0]["mean"] / max(stats.iloc[-1]["mean"], 0.0001)
                    global_insights.append({
                        "feature": col, "best_segment": stats.index[0], "worst_segment": stats.index[-1],
                        "best_conversion": stats.iloc[0]["mean"], "worst_conversion": stats.iloc[-1]["mean"], "lift": round(lift, 2)
                    })
        insight_df = pd.DataFrame(global_insights)

        return df, funnel_df, insight_df, today

    # Run Engine
    df, funnel_df, insight_df, today_date = run_full_analysis(df)

    # --- UI DISPLAY ---
    
    # ROW 1: METRICS & FUNNEL
    st.header("📊 Funnel Performance")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        worst_drop = funnel_df.dropna().sort_values("drop_percent", ascending=False).iloc[0]
        st.metric("Biggest Drop Stage", worst_drop['stage'], f"{worst_drop['drop_percent']:.1%}")
        st.write("Review the stage where leads fall off the most.")

    with col2:
        # Funnel Chart
        st.bar_chart(funnel_df.set_index("stage")["leads"])

    st.divider()

    # ROW 2: STRATEGY (LIFT)
    st.header("🌍 Global Strategy & Lift")
    if not insight_df.empty:
        top_global = insight_df.sort_values("lift", ascending=False).iloc[0]
        st.success(f"**Strategy Insight:** {top_global['feature']} is your strongest driver. **{top_global['best_segment']}** converts **{top_global['lift']}x** better than {top_global['worst_segment']}.")
        st.dataframe(insight_df, use_container_width=True)

    st.divider()

    # ROW 3: INTEGRITY AUDIT
    st.header("🛡️ Integrity Compliance Audit")
    
    checks = [
        ("Lost without 3 attempts", (df["reason"].str.contains("connect", case=False, na=False)) & (df["funnel_stage"] == "Lost") & (df.get("calls_after_latest_stage", 0).fillna(0) < 3)),
        ("CRM calls without Jerry record", (df["calldatebucket"].notna()) & (df["last_call_jerry"].isna())),
        ("Calls after lead marked lost", (df["lost_date"].notna()) & (df.get("calls_after_latest_stage", 0).fillna(0) > 0)),
        ("Missed followups", (df["followupdate"].notna()) & (df["followupdate"] < today_date) & (df.get("calls_after_followup_date", 0).fillna(0) == 0))
    ]

    for title, condition in checks:
        with st.expander(f"📍 {title}"):
            counts = df[condition].groupby("owneridname").size().reset_index(name='Violations').sort_values("Violations", ascending=False).head(5)
            if not counts.empty:
                c = alt.Chart(counts).mark_bar(color='#FF4B4B').encode(
                    x=alt.X('owneridname:N', sort='-y', title="Relationship Manager"),
                    y='Violations:Q'
                ).properties(height=200)
                st.altair_chart(c, use_container_width=True)
                st.table(counts)
            else:
                st.success("100% Compliance")

    # --- DOWNLOAD ---
    st.divider()
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Audit CSV", csv, "insight_audit.csv", "text/csv")

else:
    st.info("👋 Welcome to InsightAI. Upload a CSV to generate your automated V1 Audit.")
