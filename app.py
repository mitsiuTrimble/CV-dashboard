import json
import pandas as pd
import streamlit as st
import os
import plotly.express as px
import io
import zipfile
from PIL import Image

# --- Load APE results from JSON ---
with open("ape_results.json") as f:
    data = json.load(f)

# --- Extract structured records ---
records = []
for entry in data:
    algo = entry.get("algorithm", "")
    if "groundTruth" in algo:
        continue  # Skip groundTruth algorithms

    rel_path = entry.get("algorithm_relative_folder", "")
    folder = entry.get("folder", "")
    plot_path = os.path.basename(entry.get("plot_path", ""))

    parts = rel_path.split('/')
    if len(parts) < 2:
        continue
    tag1, tag2 = parts[0], parts[1]  # e.g., "NWC", "mp4_low"

    records.append({
        "Algorithm": algo,
        "Tag": tag1,            # This is the Jobsite for display
        "Subtag": tag2,
        "Video": folder,
        "RMSE": entry.get("rmse", None),
        "Mean": entry.get("mean", None),
        "Median": entry.get("median", None),
        "Std": entry.get("std", None),
        "Min": entry.get("min", None),
        "Max": entry.get("max", None),
        "Plot PDF": plot_path
    })

# --- Convert to DataFrame ---
df = pd.DataFrame(records)

# Define consistent subtag order
subtag_order = ["mp4_verylow", "mp4_low", "mp4_mid", "mp4_medium", "mp4_high"]
df["Subtag"] = pd.Categorical(df["Subtag"], categories=subtag_order, ordered=True)

# --- Streamlit App ---
st.set_page_config(page_title="APE Metrics Dashboard", layout="wide")
# Updated dashboard title as requested
st.title("ATLAS Absolute Pose Error (APE) Metrics Dashboard")

# --- Sidebar Filters ---
st.sidebar.header("Filters")
algorithm_options = ["All algorithms"] + sorted(df["Algorithm"].unique())
selected_algorithm = st.sidebar.selectbox("Select Algorithm", algorithm_options)

tag_options = sorted(df["Tag"].unique())
selected_tags = st.sidebar.multiselect("Select Jobsite(s)", tag_options, default=tag_options)

# Filter dataframe based on selected tags (Jobsite)
algo_df = df[df["Tag"].isin(selected_tags)]
# Further filter by algorithm if not "All algorithms"
if selected_algorithm != "All algorithms":
    algo_df = algo_df[algo_df["Algorithm"] == selected_algorithm]

# Available subtags based on filtered data
available_subtags = algo_df["Subtag"].dropna().unique().tolist()
selected_subtags = st.sidebar.multiselect("Select Subtag(s)", available_subtags, default=available_subtags)

# Final filtered dataframe based on subtags
filtered = algo_df[algo_df["Subtag"].isin(selected_subtags)]

# Text input for searching video names in the filtered dataframe
video_search = st.sidebar.text_input("Search Video Name")
if video_search:
    filtered = filtered[filtered["Video"].str.contains(video_search, case=False, na=False)]

# --- Summary Table ---
st.subheader("Mean RMSE per Algorithm (Filtered View)")
summary_df = filtered.groupby("Algorithm")["RMSE"].mean().reset_index().sort_values(by="RMSE")
# Display summary dataframe with color gradient for better visual emphasis
st.dataframe(summary_df.style.background_gradient(cmap="YlGn"), use_container_width=True)

# --- Download Filtered CSV ---
# Provide a button to download the currently filtered data as CSV
st.download_button(
    label="Download Filtered Data as CSV",
    data=filtered.to_csv(index=False).encode('utf-8'),
    file_name="APE_metrics_filtered.csv",
    mime='text/csv'
)

# --- Tabs for Metrics Visualizations ---
st.subheader("Metric Visualizations by Subtag")

# Add radio button for color grouping in bar charts, including 'Jobsite' option
color_group = st.radio("Color bars by:", options=["Video", "Algorithm", "Jobsite"])

tabs = st.tabs(["RMSE", "Mean", "Median", "Std", "Min", "Max"])
metrics = ["RMSE", "Mean", "Median", "Std", "Min", "Max"]

for tab, metric in zip(tabs, metrics):
    with tab:
        st.markdown(f"### Bar Chart of {metric} by Subtag")
        ordered_df = filtered.sort_values(by="Subtag")
        bar_fig = px.bar(
            ordered_df,
            x="Video",
            y=metric,
            color=color_group if color_group != "Jobsite" else "Tag",
            barmode="group",
            text=metric,
            category_orders={"Subtag": subtag_order},
            facet_col="Subtag",
            facet_col_spacing=0.05,
            facet_row_spacing=0.05,
            height=500,
            range_y=(0, filtered[metric].max() * 1.1 if not filtered.empty else None)
        )
        bar_fig.update_layout(xaxis_title="Video", yaxis_title=metric, xaxis_tickangle=-45)
        st.plotly_chart(bar_fig, use_container_width=True)

        st.markdown(f"### Box Plot of {metric} by Subtag")
        box_fig = px.box(
            ordered_df,
            x="Subtag",
            y=metric,
            color="Subtag",
            points="all",
            category_orders={"Subtag": subtag_order},
            height=400
        )
        st.plotly_chart(box_fig, use_container_width=True)

# --- Highlight best/worst RMSE ---
st.subheader("Filtered APE Metrics Table")
rmse_max = filtered["RMSE"].max()
rmse_min = filtered["RMSE"].min()

subtag_order_map = {v: i for i, v in enumerate(subtag_order)}
sorted_df = filtered.copy()
sorted_df["SubtagOrder"] = sorted_df["Subtag"].map(subtag_order_map)

sorted_df = sorted_df.sort_values(
    by=["Algorithm", "Tag", "Video", "SubtagOrder"]
).drop(columns=["SubtagOrder"])

# Add Preview column with images
def get_preview_image(pdf_file):
    img_file = pdf_file + ".png"
    img_path = os.path.join("plots_previews", img_file)
    if os.path.exists(img_path):
        return img_path
    else:
        return None

sorted_df["Preview"] = sorted_df["Plot PDF"].apply(get_preview_image)

# Display table without Plot PDF column, but with Preview images
display_df = sorted_df.copy()
display_df = display_df.drop(columns=["Plot PDF"])

# Replace deprecated applymap with map for styling RMSE min and max highlight
def highlight_rmse(val):
    if val == rmse_min:
        return 'background-color: yellow'
    elif val == rmse_max:
        return 'background-color: orange'
    else:
        return ''

styled_df = filtered.style.map(highlight_rmse)

# Show styled dataframe before preview table using st.data_editor for interactive sorting
st.data_editor(filtered, use_container_width=True)

# Display preview images inline with info

# --- Metrics Table with Previews (Expander, Search, Spacing, RMSE/Tag, Download) ---
# Search bar above previews
st.write("### Metrics Table with Previews")
search_text = st.text_input("🔍 Search by Algorithm or Video Name for Previews", value="", key="preview_search")
preview_df = display_df.copy()
if search_text:
    preview_df = preview_df[
        preview_df["Algorithm"].str.contains(search_text, case=False, na=False) |
        preview_df["Video"].str.contains(search_text, case=False, na=False)
    ]

# Expander set to expanded=True as requested to show previews by default
with st.expander("📊 Metrics Table with Previews (click to expand)", expanded=True):
    columns = st.columns(3)
    for i, (idx, row) in enumerate(preview_df.iterrows()):
        col_idx = i % 3
        with columns[col_idx]:
            info_text = f"**Algorithm:** {row['Algorithm']}  \n**Video:** {row['Video']}  \n**Subtag:** {row['Subtag']}"
            st.markdown(info_text)
            img_path = row["Preview"]
            if img_path and os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    st.image(img, width=400)
                    # Show RMSE and Tag below image
                    st.markdown(
                        f"<div style='margin-top: 0.5em;'><b>RMSE:</b> {row['RMSE']:.3f} &nbsp; | &nbsp; <b>Tag:</b> {row['Tag']}</div>",
                        unsafe_allow_html=True
                    )
                    # Download button for the image
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()
                    st.download_button(
                        label="Download Image",
                        data=img_bytes,
                        file_name=os.path.basename(img_path),
                        mime="image/png",
                        key=f"dl_img_{idx}"
                    )
                except Exception:
                    st.write("Image preview not available")
            else:
                st.write("No Preview")
            # Add spacing between image blocks
            st.markdown("---")

# --- Download All PDF Plots as ZIP ---
def zip_plots_directory(directory="plots"):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, directory)
                zip_file.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

# Button to download all PDF plots as a ZIP archive
if st.button("Download All PDF Plots"):
    if os.path.exists("plots") and any(os.scandir("plots")):
        zip_data = zip_plots_directory("plots")
        st.download_button(
            label="Download ZIP of All PDF Plots",
            data=zip_data,
            file_name="all_pdf_plots.zip",
            mime="application/zip"
        )
    else:
        st.warning("No PDF plots found in the 'plots' directory.")

# --- Instructions to run the dashboard locally ---
st.markdown("---")
st.markdown(
    """
    ### How to Run This Dashboard Locally

    1. **Install Python 3.7 or higher** if not already installed.

    2. **Install required packages** by running:
    ```
    pip install streamlit pandas plotly pillow
    ```

    3. **Place the following files and folders** in the same directory as this script:
       - `ape_results.json` (your data file)
       - `plots/` folder containing PDF plots
       - `plots_previews/` folder containing preview PNG images of the plots

    4. **Run the dashboard** using the command:
    ```
    streamlit run app.py
    ```

    5. **Open the URL** provided by Streamlit (usually http://localhost:8501) in your web browser.

    ---
    """
)