import os
import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

st.set_page_config(page_title="Automatic receipt analyzer", layout="centered")

# CSS
st.markdown("""
<style>
    .block-container {
        max-width: 600px !important;
        margin: 0 auto !important;
        padding-top: 2rem;
    }
    
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
        margin: 0 auto;
    }

    div[data-testid="stButton"] {
        display: flex;
        justify-content: center;
    }

    .stButton > button {
        width: 100%;
        max-width: 300px;
    }
</style>
""", unsafe_allow_html=True)

st.title("Automatic receipt analyzer")

lang = st.selectbox("Output language:", ["Ukrainian", "English", "Spanish"])
lang_codes = {"Ukrainian": "uk", "English": "en", "Spanish": "es"}
target_lang = lang_codes[lang]

uploaded_file = st.file_uploader("Upload photo", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    st.image(uploaded_file, width=300)

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'table'
if 'analyzed_data' not in st.session_state:
    st.session_state.analyzed_data = None
if 'merchant_name' not in st.session_state:
    st.session_state.merchant_name = ""

if st.button("Analyze"):
    if uploaded_file is not None:
        with st.spinner("Analyzing and translating via Gemini..."):
            try:
                gemini_api_key = os.environ.get("GEMINI_API_KEY")
                if not gemini_api_key:
                    st.error("GEMINI_API_KEY is missing in .env file!")
                    st.stop()
                    
                client = genai.Client(api_key=gemini_api_key)

                image = Image.open(uploaded_file)

                prompt = f"""
                Analyze this receipt image. 
                Extract the merchant name and all purchased line items with their original prices and discounts.
                Translate item descriptions into {lang}. Do not translate merchant name.

                Return ONLY a JSON object (without markdown codeblocks like ```json) with the following structure:
                {{
                  "merchant_name": "String",
                  "items": [
                    {{
                      "Item": "Translated item description",
                      "Old Price": float,
                      "Discount": float,
                      "Price": float
                    }}
                  ]
                }}
                Note: "Old Price" is price before discount, "Discount" is discount amount, "Price" is final price paid for item. If no discount, Discount is 0.0 and Old Price equals Price.
                """

                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=[image, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                import json
                result = json.loads(response.text)

                st.session_state.merchant_name = result.get("merchant_name", "Unknown Merchant")
                st.session_state.analyzed_data = result.get("items", [])
                st.rerun()

            except Exception as e:
                st.error(f"Error processing receipt: {e}")
    else:
        st.warning("Please upload a photo first.")

if st.session_state.analyzed_data:
    st.markdown("---")
    st.subheader(st.session_state.merchant_name)
    
    df = pd.DataFrame(st.session_state.analyzed_data)
    
    cols = ["Item", "Old Price", "Discount", "Price"]
    df = df.reindex(columns=[c for c in cols if c in df.columns])
    
    total_old = df["Old Price"].sum() if "Old Price" in df.columns else 0.0
    total_discount = df["Discount"].sum() if "Discount" in df.columns else 0.0
    total_final = df["Price"].sum() if "Price" in df.columns else 0.0
    
    if st.session_state.view_mode == 'table':
        sum_row = pd.DataFrame([{"Item": "TOTAL", "Old Price": total_old, "Discount": total_discount, "Price": total_final}])
        df_display = pd.concat([df, sum_row], ignore_index=True)
        st.dataframe(df_display, use_container_width=True)
    else:
        text_output = f"{st.session_state.merchant_name}\n"
        for _, row in df.iterrows():
            if row.get("Discount", 0) > 0:
                text_output += f"{row['Item']} {row['Old Price']:.2f} -{row['Discount']:.2f} {row['Price']:.2f}\n"
            else:
                text_output += f"{row['Item']} {row['Price']:.2f}\n"
        
        text_output += f"TOTAL "
        if total_discount > 0:
            text_output += f"{total_old:.2f} -{total_discount:.2f} "
        text_output += f"{total_final:.2f}"
        
        st.code(text_output, language="text")

    if st.session_state.view_mode == 'table':
        if st.button("switch to text view"):
            st.session_state.view_mode = 'text'
            st.rerun()
    else:
        if st.button("switch to table view"):
            st.session_state.view_mode = 'table'
            st.rerun()