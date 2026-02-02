# Tolerante file uploader met fallback
st.subheader("Upload DEGIRO CSV")
col1, col2 = st.columns([3,1])
with col1:
    uploaded_file = st.file_uploader("Kies CSV", type="csv", help="DEGIRO Account.csv ondersteund")
with col2:
    max_size_mb = st.slider("Max size (MB)", 10, 500, 200)

if uploaded_file is not None:
    if uploaded_file.size > max_size_mb * 1024 * 1024:
        st.error(f"❌ File te groot: {uploaded_file.size / (1024*1024):.1f} MB > {max_size_mb} MB")
        st.stop()
    
    # Progress bar voor vertrouwen
    progress = st.progress(0)
    status = st.empty()
    
    try:
        df = load_data(uploaded_file)
        progress.progress(100)
        status.success("✅ Upload & parse geslaagd!")
        st.success(f"Geladen: {len(df)} rijen")
        # Rest van je code hier...
    except Exception as e:
        st.error(f"Parse error: {str(e)}. Probeer ander encoding.")
        st.info("Tips: Open CSV in Notepad++, save as UTF-8 zonder BOM, ';' separator.")

# Fallback: Text paste voor kleine files
st.subheader("🆘 Alternatief: Plak CSV tekst")
csv_text = st.text_area("Plak eerste 1000 regels CSV", height=200)
if st.button("Parse geplakte tekst") and csv_text:
    try:
        df = pd.read_csv(pd.StringIO(csv_text), sep=';', encoding='utf-8')
        st.success("✅ Geparsed!")
        # Rest code...
    except:
        df = pd.read_csv(pd.StringIO(csv_text), sep=',', encoding='latin1')
