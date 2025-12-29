import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO

def retrieverrens(text):
    """
    Funktion som rensar retriever-nedladdningar (formatet ska vara utf-16)
    """
    # KRITISKT: Normalisera radbrytningar först!
    # Retriever-filer använder Windows-format (CRLF) som måste konverteras
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Rensa bort metadata
    text = re.sub(r"Linnéuniversitetet.+", "", text)
    text = re.sub(r"Datum\s.+", "", text)
    text = re.sub(r"Nyheter:", "", text)
    text = text.strip("\n")
    
    # Ta bort från originaltexten det som senare blir markör mellan artiklar
    text = re.sub(r"\|", "", text)
    
    # Samla ihop alla länkar till originalartiklar
    länkar = re.findall(r"http://ret\.nu/\w+", text)
    
    # Bryt texten i artiklar
    # Mönster som fungerar för modernt Retriever-format (med "Alla artiklar" prefix)
    text = re.sub(r"Alla artiklar.*?Läs hela artikeln på\s+http://ret\.nu/\w+\s*\n=+\s*\n+", "|", text, flags=re.DOTALL)
    
    # Alternativt mönster för Se webartikeln
    text = re.sub(r"Se webartikeln på\s+http://ret\.nu/\w+\s*\n=+\s*\n+", "|", text, flags=re.DOTALL)
    
    # Äldre mönster (för bakåtkompatibilitet med andra format)
    text = re.sub(r"©.+\n\nLäs hela.+\n=+\n\n", "|", text)
    text = re.sub(r"©.+\n\nSe webartikeln på.+\n=+\n\n", "|", text)
    
    textlista = text.split("|")
    tuplelist = []
    
    for item in textlista:
        # Extrahera tidningstitel och datum
        datum = re.findall(r"\n.+,\s\d+-\d+-\d+", item)
        sidor = re.findall(r"Sida\s\d.+", item)
        
        if len(sidor) > 0:
            sidor = sidor[0]
            item = re.sub(sidor, "", item)
        else:
            sidor = ""
        
        rentextrader = item.split("\n")
        rubrik = rentextrader[0]
        rentext = " ".join(rentextrader[3:])
        rentext = rentext.replace("Publicerat i print.", "")
        
        if len(datum) == 0:
            tuplen = (rubrik, "NA", sidor.strip("Sida "), rentext)
        else:
            tuplen = (rubrik, datum[0].strip(), sidor.strip("Sida "), rentext)
        
        tuplelist.append(tuplen)
    
    artikeldict = []
    länknr = 0
    
    for i in tuplelist:
        tiddat = i[1].split(",")
        if len(tiddat) > 2:
            tiddat = [tiddat[0] + tiddat[1], tiddat[2]]
        
        if länknr < len(länkar):
            länk = länkar[länknr]
        else:
            länk = ""
        
        artikel = {
            "rubrik": i[0],
            "tidning": tiddat[0] if len(tiddat) > 0 else "",
            "datum": tiddat[1] if len(tiddat) > 1 else "",
            "sida": i[2],
            "text": i[3],
            "länk": länk
        }
        artikeldict.append(artikel)
        länknr = länknr + 1
    
    artikelpd = pd.DataFrame(artikeldict)
    return artikelpd

# Streamlit app
st.set_page_config(page_title="Retriever Parser", page_icon="📰", layout="wide")

st.title("📰 Retriever Text Parser")
st.markdown("Ladda upp textfiler från Retriever-databasen för att extrahera och organisera artikeldata.")

# Sidebar with instructions
with st.sidebar:
    st.header("Instruktioner")
    st.markdown("""
    **Så här använder du appen:**
    
    1. Ladda upp en eller flera `.txt` filer från Retriever
    2. Filerna måste vara i UTF-16 format
    3. Förhandsgranska resultatet
    4. Ladda ner som CSV
    
    **Kolumner i output:**
    - Rubrik
    - Tidning
    - Datum
    - Sida
    - Text
    - Länk
    """)

# File uploader
uploaded_files = st.file_uploader(
    "Välj Retriever textfiler (.txt)",
    type=['txt'],
    accept_multiple_files=True,
    help="Du kan ladda upp flera filer samtidigt"
)

if uploaded_files:
    # Combine all uploaded files
    combined_text = ""
    
    with st.spinner("Läser in filer..."):
        for uploaded_file in uploaded_files:
            try:
                # Reset file pointer to beginning
                uploaded_file.seek(0)
                
                # Read as bytes first
                bytes_data = uploaded_file.read()
                
                # Try UTF-16 decoding
                try:
                    text = bytes_data.decode('utf-16')
                    combined_text = combined_text + " " + text
                    st.success(f"✓ Läste in: {uploaded_file.name} ({len(text):,} tecken)")
                except UnicodeDecodeError:
                    # Try UTF-8 as fallback
                    try:
                        text = bytes_data.decode('utf-8')
                        combined_text = combined_text + " " + text
                        st.warning(f"⚠️ Läste {uploaded_file.name} som UTF-8 (förväntat UTF-16)")
                    except UnicodeDecodeError:
                        st.error(f"✗ Kunde inte läsa {uploaded_file.name} - felaktigt format")
                        
            except Exception as e:
                st.error(f"✗ Kunde inte läsa {uploaded_file.name}: {str(e)}")
    
    if combined_text:
        # Parse the text
        with st.spinner("Bearbetar text..."):
            try:
                df = retrieverrens(combined_text)
                
                st.success(f"✓ Hittade {len(df)} artiklar!")
                
                # Display statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Antal artiklar", len(df))
                with col2:
                    st.metric("Antal tidningar", df['tidning'].nunique())
                with col3:
                    if len(df) > 0 and df['datum'].notna().any():
                        date_range = f"{df['datum'].min()} → {df['datum'].max()}"
                    else:
                        date_range = "N/A"
                    st.metric("Datumspann", date_range)
                
                # Display preview
                st.subheader("Förhandsgranskning")
                
                # Filter options
                with st.expander("🔍 Filter och sökning"):
                    col1, col2 = st.columns(2)
                    with col1:
                        search_term = st.text_input("Sök i rubriker eller text", "")
                    with col2:
                        selected_tidning = st.multiselect(
                            "Filtrera på tidning",
                            options=sorted(df['tidning'].unique())
                        )
                
                # Apply filters
                filtered_df = df.copy()
                if search_term:
                    mask = (
                        filtered_df['rubrik'].str.contains(search_term, case=False, na=False) |
                        filtered_df['text'].str.contains(search_term, case=False, na=False)
                    )
                    filtered_df = filtered_df[mask]
                
                if selected_tidning:
                    filtered_df = filtered_df[filtered_df['tidning'].isin(selected_tidning)]
                
                st.info(f"Visar {len(filtered_df)} av {len(df)} artiklar")
                
                # Display dataframe
                st.dataframe(
                    filtered_df,
                    use_container_width=True,
                    height=400,
                    column_config={
                        "länk": st.column_config.LinkColumn("Länk"),
                        "text": st.column_config.TextColumn(
                            "Text",
                            width="large",
                        ),
                    }
                )
                
                # Download section
                st.subheader("Ladda ner")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Download full dataset as CSV
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Ladda ner CSV",
                        data=csv,
                        file_name="retriever_export.csv",
                        mime="text/csv",
                    )
                
                with col2:
                    # Download full dataset as Excel
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Artiklar')
                    excel_data = excel_buffer.getvalue()
                    st.download_button(
                        label="📥 Ladda ner Excel",
                        data=excel_data,
                        file_name="retriever_export.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                
                with col3:
                    # Download filtered dataset
                    if len(filtered_df) < len(df):
                        st.markdown("**Filtrerad data:**")
                        
                        # CSV
                        filtered_csv = filtered_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 CSV (filtrerad)",
                            data=filtered_csv,
                            file_name="retriever_filtered.csv",
                            mime="text/csv",
                            key="filtered_csv"
                        )
                        
                        # Excel
                        filtered_excel_buffer = BytesIO()
                        with pd.ExcelWriter(filtered_excel_buffer, engine='openpyxl') as writer:
                            filtered_df.to_excel(writer, index=False, sheet_name='Artiklar')
                        filtered_excel_data = filtered_excel_buffer.getvalue()
                        st.download_button(
                            label="📥 Excel (filtrerad)",
                            data=filtered_excel_data,
                            file_name="retriever_filtered.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="filtered_excel"
                        )
                
            except Exception as e:
                st.error(f"Ett fel uppstod vid bearbetning: {str(e)}")
                st.exception(e)
else:
    st.info("👆 Ladda upp en eller flera Retriever textfiler för att komma igång")
    
    # Show example
    with st.expander("📖 Visa exempel på förväntad filstruktur"):
        st.code("""
Linnéuniversitetet BIBSAM (Växjö Universitet Kalmar Högskola)
Uttag 2020-01-28

Nyheter:

... och här är ytterligare 50 förebilder att inspireras av
Nya Dagen, 2006-12-29
Sida 10#11
Publicerat i print.

[Artikeltext här...]

Alla artiklar är skyddade av upphovsrättslagen...
Läs hela artikeln på
http://ret.nu/nS45H0r6
==============================================================================

[Nästa artikel...]
        """)

# Footer
st.markdown("---")
st.markdown(
    "Skapad för att bearbeta textfiler från Retriever-databasen | "
    "Baserad på original Colab notebook"
)
