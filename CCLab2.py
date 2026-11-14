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
                Analyze this image. First, determine if it is a valid receipt, bill, or invoice.
                If it is NOT a receipt (random text or photo), set "is_receipt" to false, leave "merchant_name" empty, "items" empty.
                
                If it IS a valid receipt:
                Set "is_receipt" to true.
                Extract the merchant name and all purchased line items with their unit price, quantity, and total price for the line.
                Translate item descriptions into {lang}. Do not translate merchant name.

                Return ONLY a JSON object (without markdown codeblocks like ```json) with the following structure:
                {{
                  "is_receipt": boolean,
                  "merchant_name": "String",
                  "items": [
                    {{
                      "Item": "Translated item description",
                      "Price": float,
                      "Quantity": float,
                      "Total": float
                    }}
                  ]
                }}
                Note: "Price" is the price for a single unit/item, "Quantity" is the quantity or weight purchased (default to 1 if not specified on the receipt), and "Total" is the total price paid for this line item (Price * Quantity).
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

                if not result.get("is_receipt", False):
                    st.session_state.analyzed_data = None
                    st.session_state.merchant_name = ""
                    err_msg = "Receipt not recognized."
                    st.error(err_msg)
                else:
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
    
    cols = ["Item", "Price", "Quantity", "Total"]
    df = df.reindex(columns=[c for c in cols if c in df.columns])
    
    total_quantity = df["Quantity"].sum() if "Quantity" in df.columns else 0
    total_sum = df["Total"].sum() if "Total" in df.columns else 0.0
    
    if st.session_state.view_mode == 'table':
        sum_row = pd.DataFrame([{
            "Item": "TOTAL", 
            "Price": None, 
            "Quantity": total_quantity, 
            "Total": total_sum
        }])
        df_display = pd.concat([df, sum_row], ignore_index=True)
        st.dataframe(df_display, width='stretch')
    else:
        text_output = f"{st.session_state.merchant_name}\n"
        for _, row in df.iterrows():
            price = row.get("Price", 0.0)
            quantity = row.get("Quantity", 1)
            total = row.get("Total", 0.0)
            
            quantity_str = f"{int(quantity)}" if float(quantity).is_integer() else f"{quantity}"
            
            if quantity != 1:
                text_output += f"{row['Item']} — {price:.2f} x {quantity_str} = {total:.2f}\n"
            else:
                text_output += f"{row['Item']} — {total:.2f}\n"
        
        total_quantity_str = f"{int(total_quantity)}" if float(total_quantity).is_integer() else f"{total_quantity}"
        text_output += f"\nTOTAL ({total_quantity_str} items): {total_sum:.2f}"
        
        st.code(text_output, language="text")

    if st.session_state.view_mode == 'table':
        if st.button("switch to text view"):
            st.session_state.view_mode = 'text'
            st.rerun()
    else:
        if st.button("switch to table view"):
            st.session_state.view_mode = 'table'
            st.rerun()
