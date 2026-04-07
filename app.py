import streamlit as st
import boto3
import json

# ==============================
# 🔐 LOAD SECRETS
# ==============================
AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_SESSION_TOKEN = st.secrets.get("AWS_SESSION_TOKEN", None)
AWS_REGION = st.secrets["AWS_DEFAULT_REGION"]

BUCKET_NAME = "vqb-doc-converter"
PREFIX = "tech-docs/"

# ==============================
# 🎨 UI
# ==============================
st.markdown("""
<style>
.stApp { background-color: #f0ede6; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("📄 Capability Packet Generator")

# ==============================
# ☁️ S3 CLIENT
# ==============================
def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        region_name=AWS_REGION
    )

# ==============================
# 📂 LIST FILES
# ==============================
def list_s3_documents():
    try:
        s3 = get_s3_client()

        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=PREFIX
        )

        files = []

        for obj in response.get("Contents", []):
            key = obj["Key"]
            if key.endswith((".txt", ".md")):
                name = key.replace(PREFIX, "")
                files.append({"key": key, "name": name})

        return files

    except Exception as e:
        st.error(f"S3 Error: {str(e)}")
        return []

# ==============================
# 📄 READ FILE FROM S3
# ==============================
def read_s3_file(key):
    try:
        s3 = get_s3_client()
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception as e:
        st.error(f"File Read Error: {str(e)}")
        return ""

# ==============================
# 🤖 CLAUDE (BEDROCK) CALL
# ==============================
def call_claude(prompt):
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN
        )

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        })

        response = client.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=body
        )

        result = json.loads(response["body"].read())

        return result["content"][0]["text"]

    except Exception as e:
        st.error(f"Claude Error: {str(e)}")
        return ""

# ==============================
# ⚙️ GENERATE PACKET
# ==============================
def generate_capability_packet(text):

    prompt = f"""
    Convert the below content into JSON format with:
    title, summary, features (list)

    Content:
    {text}
    """

    raw = call_claude(prompt)

    if not raw:
        return {}

    raw = raw.strip()

    # Remove markdown ```json
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except:
        st.error("JSON parsing failed")
        st.text(raw[:1000])
        return {}

# ==============================
# 🚀 MAIN FLOW
# ==============================
files = list_s3_documents()

if not files:
    st.warning("No files found in S3")
else:
    file_names = [f["name"] for f in files]

    selected_name = st.selectbox("Select a document", file_names)
    selected_file = next(f for f in files if f["name"] == selected_name)

    if st.button("Generate 🚀"):

        with st.spinner("Reading file..."):
            text = read_s3_file(selected_file["key"])

        if not text:
            st.stop()

        with st.spinner("Generating with Claude..."):
            result = generate_capability_packet(text)

        if result:
            st.success("Done!")

            st.subheader("Title")
            st.write(result.get("title", ""))

            st.subheader("Summary")
            st.write(result.get("summary", ""))

            st.subheader("Features")
            for f in result.get("features", []):
                st.write(f"- {f}")

            st.download_button(
                "Download JSON",
                json.dumps(result, indent=2),
                file_name="capability.json"
            )
