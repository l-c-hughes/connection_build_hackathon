import streamlit as st
from streamlit.connections import ExperimentalBaseConnection
from deta import Deta
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import random
import requests

app_palette = ["#f7f7fe","#85ffc7","#4281a4","#b2abf2"]

st.set_page_config(page_title="Workout Data Tracker",page_icon=":muscle:",layout="wide")

class BaseConn(ExperimentalBaseConnection[Deta.Base]):

    def __init__(self, project_key):
        self.project_key = project_key

    def _connect(self):
        deta = Deta(self.project_key)
        return deta.Base("workout_data")

    def cursor(self):
        return self._connect()

    @st.cache_data(ttl="1d",show_spinner=False)
    def get_data(_self, key):
        cursor = _self._connect()
        return cursor.get(key)
    
    def put_data(self, data):
        cursor = self._connect()
        cursor.put(data)

    def fetch_data(self):
        cursor = self._connect()
        fetched = cursor.fetch().items
        return fetched

class ApiNinjasConn(ExperimentalBaseConnection):

    def __init__(self, api_key):
        self.api_key = api_key

    def _connect(self):
        return self

    def _get_headers(self):
        return {"X-Api-Key": f"{self.api_key}"}
    
    @st.cache_data(ttl=604800)
    def get_response(_self, endpoint):
        url = f"https://api.api-ninjas.com/v1/exercises?muscle={endpoint}"
        headers = _self._get_headers()
        response = requests.get(url, headers=headers)
        idx = random.randint(0, 9)
        if response.status_code == requests.codes.ok:
            return response.json()[idx]
        else:
            print("Error:", response.status_code, response.text)

def main():

    # Initialise connections
    db = BaseConn(st.secrets["db_credentials"]["db_key"])
    api = ApiNinjasConn(st.secrets["api_keys"]["api_key"])

    # Function for new database entries
    def log_workout(date, length, areas_worked_out):
        return db.put_data({"key":date.isoformat(),"length":length,"areas_worked_out":areas_worked_out})
    
    # Function to format times
    def format_time(minutes):
        hrs = minutes // 60
        mins = minutes % 60
        return hrs, mins
    
    # Categorising function
    def categorize_area(area):
        if area in ["abdominals"]:
            return "core"
        elif area in ["chest", "biceps", "triceps", "traps"]:
            return "upper body"
        elif area in ["calves", "glutes", "quadriceps"]:
            return "lower body"
        else:
            return "other"

    # Fetch data from database
    db_all = list(db.fetch_data())
    df_all = pd.DataFrame(db_all)

    # Defining app visualisations

    # Fig1: Day / workout length area chart for this week

    start_of_week = datetime.now() - timedelta(days=datetime.now().weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week = [start_of_week + timedelta(days=i) for i in range(7)]
    week = pd.Series(week).apply(lambda x: x.date())

    df_all["key"] = df_all["key"].apply(lambda x:datetime.strptime(x, "%Y-%m-%d").date())
    df_all.rename(columns={"key":"date"},inplace=True)

    now_week_df = df_all[df_all["date"].isin(week)]
    now_week_cum = pd.DataFrame({"date":week})
    now_week_cum["length"] = now_week_cum["date"].apply(lambda x: now_week_df[now_week_df["date"] <= x]["length"].sum())

    week_area = go.Figure()
    week_area.add_trace(go.Scatter(x=now_week_cum["date"], y=now_week_cum["length"],line_color=app_palette[1],
                            fill="tozeroy",mode="lines",opacity = 0.5))
    week_area.update_layout(
        margin=dict(t=0),
        xaxis=dict(showgrid=False),
        xaxis_title="Day",
        yaxis=dict(showgrid=False),
        yaxis_title="Workout Time", 
        showlegend=False
    )

    # Fig 2: Area Chart for Last Week 

    start_of_last_week = start_of_week - timedelta(weeks=1)
    end_of_last_week = end_of_week - timedelta(weeks=1)

    last_week = [start_of_last_week + timedelta(days=i) for i in range(7)]
    last_week = pd.Series(last_week).apply(lambda x: x.date())

    last_week_df = df_all[df_all["date"].isin(last_week)]
    last_week_cum = pd.DataFrame({"date":last_week})
    last_week_cum["length"] = last_week_cum["date"].apply(lambda x: last_week_df[last_week_df["date"] <= x]["length"].sum())

    last_week_area = go.Figure()
    last_week_area.add_trace(go.Scatter(x=last_week_cum["date"], y=last_week_cum["length"], line_color=app_palette[3],
                            fill="tozeroy",mode="lines",opacity = 0.5))
    last_week_area.update_layout(
        margin=dict(t=0),
        xaxis=dict(showgrid=False),
        xaxis_title="Day",
        yaxis=dict(showgrid=False),
        yaxis_title="Workout Time", 
        showlegend=False
    )

    # Fig 3: Area chart for month

    today = datetime.now().date()
    start_of_month = today.replace(day=1)
    not_this_month = start_of_month.replace(day=28) + timedelta(days=4)
    end_of_month = not_this_month - timedelta(days=not_this_month.day)
    month_dates = pd.date_range(start=start_of_month, end=end_of_month, freq="D").date

    month_df = df_all[df_all["date"].isin(month_dates)]
    month_df = pd.DataFrame({"date":month_dates})
    month_df = month_df.merge(df_all, on="date", how="left")
    month_df = month_df[["date","length"]]
    month_df["length"] = month_df["length"].fillna(0)

    month_fig = go.Figure()
    month_fig.add_trace(go.Bar(x=month_df["date"], y=month_df["length"]))
    month_fig.update_traces(marker_color=app_palette[1], opacity=1,name="Workout")

    month_fig.update_layout(
        margin=dict(t=0),
        xaxis=dict(showgrid=False),
        xaxis_title="Day",
        yaxis=dict(showgrid=False),
        yaxis_title="Workout Time (Mins)", 
        showlegend=False
    )
    month_df["date"] = pd.to_datetime(month_df["date"])
    month_df_weekly = month_df.resample("W", on="date").mean().reset_index()

    month_fig.add_trace(go.Scatter(x=month_df_weekly["date"], y=month_df_weekly["length"], name="Weekly Average", line_color=app_palette[1],
                            fill="tozeroy",mode="lines",opacity = 0.5))

    # Fig 4: Area chart for last month

    start_last_month = start_of_month - timedelta(days=1)
    last_month_start = start_last_month.replace(day=1)
    end_last_month = start_of_month - timedelta(days=1)
    last_month_dates = pd.date_range(start=last_month_start, end=end_last_month, freq="D").date

    last_month_df = df_all[df_all["date"].isin(last_month_dates)]
    last_month_df = pd.DataFrame({"date":last_month_dates})
    last_month_df = last_month_df.merge(df_all, on="date", how="left")
    last_month_df = last_month_df[["date","length"]]
    last_month_df["length"] = last_month_df["length"].fillna(0)

    last_month_fig = go.Figure()
    last_month_fig.add_trace(go.Bar(x=last_month_df["date"], y=last_month_df["length"]))
    last_month_fig.update_traces(marker_color=app_palette[3], opacity=1,name="Workout")

    last_month_fig.update_layout(
        margin=dict(t=0),
        xaxis=dict(showgrid=False),
        xaxis_title="Day",
        yaxis=dict(showgrid=False),
        yaxis_title="Workout Time (Mins)", 
        showlegend=False
    )
    last_month_df["date"] = pd.to_datetime(last_month_df["date"])
    last_month_weekly = last_month_df.resample("W", on="date").mean().reset_index()

    last_month_fig.add_trace(go.Scatter(x=last_month_weekly["date"], y=last_month_weekly["length"], name="Weekly Average", line_color=app_palette[3],
                            fill="tozeroy",mode="lines",opacity = 0.5))
    
    # Fig 5: Isotype chart for last 14 days

    recent_period = today - timedelta(days=14)
    recent_df = df_all[df_all['date'] >= recent_period]
    cat_df = recent_df.explode("areas_worked_out")
    cat_df['category'] = cat_df['areas_worked_out'].apply(categorize_area)

    iso_frame = pd.DataFrame(
        {
            "Count":[
                "🏋️" * cat_df[cat_df['category'] == 'upper body'].shape[0],
                "🚴" * cat_df[cat_df['category'] == 'lower body'].shape[0],
                "🚣‍♂️" * cat_df[cat_df['category'] == 'core'].shape[0]
            ]    
        }, index=["Upper Body","Lower Body","Core"]
    )

    # APP LAYOUT
    blank_col_left,emoji_col,blank_col_right = st.columns([3,1,3])
    with emoji_col:
        st.header(":muscle:")
    blank_col_left,title_col,blank_col_right = st.columns([1,2,1])
    with title_col:
        st.title("Workout Data Tracker")
    st.title("")

    # Input Form Panel

    with st.container():
        blank_col_left,formcol,blank_col_right = st.columns([1,3,1])
        with formcol:
            with st.expander("Log Today's Workout",expanded=False):
                with st.form(key="workout_tracker",clear_on_submit=True):
                    length = st.slider("How many mins (approx) did you work out?",10,180,step=10,value=round(df_all["length"].mean()/10)*10)
                    areas_worked_out = st.multiselect("What areas did you target?",["chest","abdominals","biceps","triceps","calves","quadriceps","glutes","traps"])
                    save = st.form_submit_button("Save & Log")
                    if save:
                        date = datetime.now().date()
                        log_workout(date, length, areas_worked_out)
                        st.write(f"Workout for {date} logged. Well done!")
        st.title("")

    # Recommendation Panel

    min_area = cat_df["areas_worked_out"].value_counts().idxmin()
    suggest = api.get_response(min_area)
    emoji_dict = {"core":"🚣‍♂️","upper body":"🏋️","lower body":"🚴"}
    area_emoji = categorize_area(suggest["muscle"])

    with st.container():
        st.header("Next Workout")
        st.write("")
        breakdown,recommendation=st.columns(2)
        with breakdown:
            st.subheader("Areas Most Targeted:")
            st.dataframe(iso_frame)
        with recommendation:
            tablecol,buttoncol = st.columns([2,1])
            with tablecol:
                st.subheader(f"Try This: {emoji_dict[area_emoji]}")
                if suggest is not None:
                    st.markdown(suggest["name"])
                    st.caption(f'Area Targeted: {suggest["muscle"]}')
                    st.caption(f'Equipment Used: {suggest["equipment"]}')
                    st.caption(f'Difficulty: {suggest["difficulty"]}')
                    with st.expander("Instructions"):
                        st.write(suggest["instructions"])
                else:
                    st.write("No recommendation available.")
            with buttoncol:
                st.header(" ")
                if st.button("Get New Suggestion"):
                    api.get_response.clear()
    
    # Analytics Panel

    with st.container():

        st.header("Your Stats")
        weektab, monthtab = st.tabs(["Week","Month"])

    with weektab:

        subheadcol,metriccol = st.columns(2)
        with subheadcol:
            st.subheader("This Week")
        with metriccol:
            hrs1, mins1 = format_time(now_week_cum["length"].max())
            st.metric(label='Workout Time',value=f"{hrs1}H {mins1}M",delta=str(now_week_cum["length"].max() - last_week_cum["length"].max())+"M")
        st.plotly_chart(week_area,use_container_width=True,config={'displayModeBar': False})

        subheadcol2,metriccol2 = st.columns(2)
        with subheadcol2:
            st.subheader("Last Week")
        with metriccol2:
            hrs2, mins2 = format_time(last_week_cum["length"].max())
            st.metric(label='Workout Time',value=f"{hrs2}H {mins2}M",delta=None)
        st.plotly_chart(last_week_area,use_container_width=True,config={'displayModeBar': False})

    with monthtab:
        subheadcol3,metriccol3 = st.columns(2)
        with subheadcol3:
            st.subheader("This Month")
        with metriccol3:
            hrs3, mins3 = format_time(month_df["length"].sum())
            st.metric(label='Workout Time',value=f"{hrs1}H {mins1}M",delta=str(month_df["length"].sum() - last_month_df["length"].sum())+"M")                      
        st.plotly_chart(month_fig,use_container_width=True,config={'displayModeBar': False})

        subheadcol4,metriccol4 = st.columns(2)
        with subheadcol4:
            st.subheader("Last Month")
        with metriccol4:
            hrs4, mins4 = format_time(last_month_df["length"].sum())
            st.metric(label='Workout Time',value=f"{hrs4}H {mins4}M")              
        st.plotly_chart(last_month_fig,use_container_width=True,config={'displayModeBar': False})

if __name__ == "__main__":
    main()