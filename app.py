import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- PAGE CONFIG ---
st.set_page_config(page_title="InsightAI | V1 Sales Audit", layout="wide")

st.title("🛡️ InsightAI: Triple-Engine Audit")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("Data Control Center")
uploaded_file = st.sidebar.file_uploader("Upload CRM Export (CSV)", type="csv")

if uploaded_file is not None:
    try:
        # 1. LOAD & STANDARDIZE
        df = pd.read_csv(uploaded_file)
        df.columns = (df.columns.str.lower().str.replace(" ", "_").str.replace("(", "").str.replace(")", ""))
        
        # MAPPING LOGIC
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
        df["followupdate"] = pd.to_datetime(df["followupdate"], errors="coerce")
        today = pd.Timestamp.today()

        # --- ENGINE 1: GLOBAL STRATEGY ---
        st.header("🌍 Engine 1: Global Strategy")
        features = ["nf_task_fin", "nf_type_fin", "owneridname", "srt_bucket"]
        global_insights = []
        for col in features:
            if col in df.columns:
                stats = df.groupby(col)["converted"].agg(["mean","count"])
                stats = stats[stats["count"] >= 20].sort_values("mean", ascending=False)
                if len(stats) >= 2:
                    lift = stats.iloc[0]["mean"] / max(stats.iloc[-1]["mean"], 0.0001)
                    global_insights.append({"Feature": col, "Best": stats.index[0], "Worst": stats.index[-1], "Lift": lift})
        
        if global_insights:
            top_g = sorted(global_insights, key=lambda x: x['Lift'], reverse=True)[0]
            st.success(f"**Top Lever:** {top_g['Feature']} | **{top_g['Best']}** is converting **{top_g['Lift']:.2f}x** better than {top_g['Worst']}.")
            st.dataframe(pd.DataFrame(global_insights), use_container_width=True)

        st.markdown("---")

        # --- ENGINE 2: FUNNEL DYNAMICS ---
        st.header("📊 Engine 2: Funnel Dynamics")
        stage_transitions = [("Qualified", "APNS"), ("APNS", "App Start"), ("App Start", "RTS"), ("RTS", "Bank Prospect"), ("Bank Prospect", "Login")]
        
        results = []
        for from_s, to_s in stage_transitions:
            temp = df[df["stage_rank"] >= stage_order[from_s]].copy()
            temp["stage_conversion"] = (temp["stage_rank"] >= stage_order[to_s]).astype(int)
            for col in features:
                if col in temp.columns:
                    s = temp.groupby(col)["stage_conversion"].agg(["mean","count"])
                    s = s[s["count"] >= 15]
                    if len(s) >= 2:
                        s = s.sort_values("mean", ascending=False)
                        results.append({"Transition": f"{from_s} → {to_s}", "Feature": col, "Best": s.index[0], "Worst": s.index[-1], "Lift": s.iloc[0]["mean"]/max(s.iloc[-1]["mean"], 0.0001)})

        if results:
            st.write("**Top 5 Transition Lifts**")
            st.table(pd.DataFrame(results).sort_values("Lift", ascending=False).head(5))
        
        funnel_counts = [df[df["stage_rank"] >= stage_order[s]].shape[0] for s in stage_order.keys()]
        st.bar_chart(pd.DataFrame({"Stage": list(stage_order.keys()), "Leads": funnel_counts}).set_index("Stage"))

        st.markdown("---")

        # --- ENGINE 3: THE 5-POINT INTEGRITY AUDIT ---
        st.header("🛡️ Engine 3: Integrity & Compliance")
        
        # Defining the 5 Specific Checks
        checks = [
            ("Lost without 3 attempts", 
             (df["reason"].str.contains("connect", case=False, na=False)) & (df["max_stage"] != "Login") & (df.get("calls_after_latest_stage", 0).fillna(0) < 3)),
            
            ("CRM calls without Jerry record", 
             (df["calldatebucket"].notna()) & (df["last_call_jerry"].isna())),
            
            ("Calls after lead marked lost", 
             (df["lost_date"].notna()) & (df.get("calls_after_latest_stage", 0).fillna(0) > 0)),
            
            ("Missed followups (Active Leads)", 
             (df["followupdate"] < today) & (df["max_stage"] != "Login") & (df.get("calls_after_followup_date", 0).fillna(0) == 0)),
            
            ("High SRT delay (>15 days)", 
             (df["srt_bucket"] == ">15 days"))
        ]

        # Display in a clean grid
        cols = st.columns(2)
        for i, (title, condition) in enumerate(checks):
            with cols[i % 2]:
                st.subheader(f"📍 {title}")
                violators = df[condition].groupby("owneridname").size().sort_values(ascending=False).head(5)
                if not violators.empty:
                    st.table(violators.reset_index(name="Count"))
                else:
                    st.success("100% Compliance")

    except Exception as e:
        st.error(f"Engine Failure: {e}")
else:
    st.info("👋 Systems Ready. Please upload CRM data in the sidebar.")
