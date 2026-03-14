import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="InsightAI V1", layout="wide")
st.title("🛡️ InsightAI: Sales Performance Insights")

uploaded_file = st.sidebar.file_uploader("Upload CRM Export (CSV)", type="csv")

if uploaded_file is not None:
    try:
        # 1. LOAD & CLEAN
        df = pd.read_csv(uploaded_file)
        df.columns = (df.columns.str.lower().str.replace(" ", "_").str.replace("(", "").str.replace(")", ""))
        
        # 2. COLAB MAPPING & LOGIC
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

        # 3. THE ANALYTICAL ENGINE (TOP 5 STAGE INSIGHTS)
        st.header("📈 Top 5 Stage-to-Stage Insights")
        
        stage_transitions = [
            ("Qualified", "APNS"),
            ("APNS", "App Start"),
            ("App Start", "RTS"),
            ("RTS", "Bank Prospect"),
            ("Bank Prospect", "Login")
        ]

        features = ["nf_task_fin", "nf_type_fin", "owneridname", "srt_bucket"]
        results = []

        for from_stage, to_stage in stage_transitions:
            from_rank = stage_order[from_stage]
            to_rank = stage_order[to_stage]
            
            # Filter leads that at least reached the "From" stage
            temp = df[df["stage_rank"] >= from_rank].copy()
            temp["stage_conversion"] = (temp["stage_rank"] >= to_rank).astype(int)

            for col in features:
                if col in temp.columns:
                    stats = temp.groupby(col)["stage_conversion"].agg(["mean","count"])
                    stats = stats[stats["count"] >= 15] # Minimum sample size
                    
                    if len(stats) >= 2:
                        stats = stats.sort_values("mean", ascending=False)
                        top = stats.iloc[0]
                        bottom = stats.iloc[-1]
                        lift = top["mean"] / max(bottom["mean"], 0.0001)

                        results.append({
                            "Transition": f"{from_stage} → {to_stage}",
                            "Feature": col,
                            "Best Segment": stats.index[0],
                            "Worst Segment": stats.index[-1],
                            "Best Conv": top["mean"],
                            "Worst Conv": bottom["mean"],
                            "Lift": lift
                        })

        # Displaying the Results as a Leaderboard
        if results:
            insight_df = pd.DataFrame(results).sort_values("Lift", ascending=False).head(5)
            
            for i, row in enumerate(insight_df.to_dict('records'), 1):
                with st.container():
                    col_a, col_b = st.columns([1, 4])
                    col_a.metric(f"Rank #{i}", f"{row['Lift']:.2f}x")
                    col_b.markdown(f"### {row['Transition']} | {row['Feature']}")
                    col_b.write(f"🏆 **{row['Best Segment']}** ({row['Best Conv']:.1%}) is significantly outperforming **{row['Worst Segment']}** ({row['Worst Conv']:.1%})")
                    st.divider()
        else:
            st.warning("Not enough data to generate Lift insights. Try a larger CSV.")

        # 4. INTEGRITY SECTION
        st.header("🛡️ Integrity Violations")
        if "owneridname" in df.columns:
            violations = df.groupby("owneridname").size().reset_index(name='Total').sort_values("Total", ascending=False).head(5)
            st.table(violations)

    except Exception as e:
        st.error(f"Error: {e}")

else:
    st.info("👋 App is live! Please upload your CSV in the sidebar to view the Top 5 Insights.")
