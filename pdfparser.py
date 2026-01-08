import streamlit as st
import re
import pandas as pd
from io import BytesIO
import pdfplumber
from datetime import datetime

def extract_toc_from_pdf(pdf_file):
    """Extract table of contents with article metadata"""
    articles_toc = []
    
    with pdfplumber.open(pdf_file) as pdf:
        # Extract TOC - read until we find the first article page
        # TOC pages have many lines with date+page pattern
        # Article pages have different structure
        toc_text = ""
        toc_end_page = 4  # Default minimum
        
        for page_num in range(min(30, len(pdf.pages))):
            page_text = pdf.pages[page_num].extract_text()
            
            # Count lines that look like TOC entries
            lines = page_text.split('\n')
            toc_like_lines = sum(1 for line in lines 
                                if re.search(r'\d{4}-\d{2}-\d{2}\s+\d{1,4}$', line.strip()))
            
            # If this page has very few TOC lines and we've read at least 4 pages,
            # we've probably reached the articles section
            if toc_like_lines < 5 and page_num >= 4:
                toc_end_page = page_num
                break
            
            toc_text += page_text + "\n"
            toc_end_page = page_num + 1
        
        lines = toc_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip headers and section markers
            if not line or 'Kandidatuppsats' in line or 'Datum 2026' in line or 'Tidningsartiklar' in line:
                continue
            if line in ['heder, hedersrelaterat', 'Tidningar', 'Tidning', 'Heders', 'Allehanda', 'Socialdemokraten', 'Nyheter', 'Nyheter -']:
                continue
            
            # Pattern: Title \ue618 Source Date PageNumber
            if '\ue618' in line:
                parts = line.split('\ue618')
                
                # Skip continuation entries
                if parts[0].strip() == '':
                    continue
                
                if len(parts) >= 2:
                    title = parts[0].strip()
                    rest = parts[1].strip()
                    
                    match = re.search(r'^(.+?)\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,3})$', rest)
                    if match:
                        source = match.group(1).strip()
                        date = match.group(2)
                        page_num = int(match.group(3))
                        
                        articles_toc.append({
                            'title': title,
                            'source': source,
                            'date': date,
                            'page': page_num
                        })
    
    return articles_toc


def extract_hyperlinks_by_page(pdf_file):
    """Extract hyperlinks organized by page"""
    links_by_page = {}
    
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            links_by_page[page_num] = []
            if page.annots:
                for annot in page.annots:
                    if annot.get('uri'):
                        links_by_page[page_num].append(annot['uri'])
    
    return links_by_page


def parse_retriever_pdf(pdf_file):
    """Parse Retriever PDF using TOC for article identification"""
    
    # Extract TOC
    articles_toc = extract_toc_from_pdf(pdf_file)
    
    # Extract hyperlinks by page
    links_by_page = extract_hyperlinks_by_page(pdf_file)
    
    articles = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for toc_idx, toc_entry in enumerate(articles_toc):
            page_num = toc_entry['page'] - 1  # PDF pages are 0-indexed
            
            if page_num >= len(pdf.pages):
                continue
            
            # Extract text from article's starting page
            page = pdf.pages[page_num]
            page_text = page.extract_text()
            
            lines = page_text.split('\n')
            lines = [line.strip() for line in lines if line.strip()]
            
            # Remove the header line
            lines = [line for line in lines if 
                     'Tidningsartiklar - Kandidatuppsats' not in line and
                     not line.startswith('Datum 2026')]
            
            # Structure:
            # Line 0 (or 0-1): Title (may span multiple lines)
            # Next line: Source | info | date | Sida: X
            # Next line: Author
            # Rest: Article text
            
            author = ""
            article_text = []
            
            # Find the source line (has | and Sida:)
            source_line_idx = None
            for i, line in enumerate(lines):
                if '|' in line and ('Sida:' in line or 'Sida ' in line):
                    source_line_idx = i
                    break
            
            if source_line_idx is not None:
                # Author is the line after source line
                if source_line_idx + 1 < len(lines):
                    potential_author = lines[source_line_idx + 1]
                    
                    # Author: 1-6 words, not ending in period, not copyright
                    words = potential_author.split()
                    if (len(words) >= 1 and len(words) <= 6 and
                        len(potential_author) < 100 and
                        not potential_author.endswith('.') and
                        'Optional[©' not in potential_author and
                        'Alla artiklar är skyddade' not in potential_author):
                        author = potential_author
                        text_start_idx = source_line_idx + 2
                    else:
                        text_start_idx = source_line_idx + 1
                else:
                    text_start_idx = source_line_idx + 1
                
                # Collect text from first page
                for line in lines[text_start_idx:]:
                    # Stop at copyright markers
                    if ('Optional[©' in line or 
                        'Alla artiklar är skyddade' in line or 
                        'Klicka här för att' in line):
                        break
                    article_text.append(line)
            
            # Check if article continues on next page(s)
            next_article_page = None
            if toc_idx + 1 < len(articles_toc):
                next_article_page = articles_toc[toc_idx + 1]['page'] - 1
            
            # Continue reading subsequent pages
            current_page = page_num + 1
            max_pages = 10  # Safety limit
            pages_read = 0
            
            while current_page < len(pdf.pages) and pages_read < max_pages:
                # Stop if we've reached the next article
                if next_article_page and current_page >= next_article_page:
                    break
                
                page = pdf.pages[current_page]
                page_text = page.extract_text()
                
                lines = page_text.split('\n')
                lines = [line.strip() for line in lines if line.strip()]
                
                # Remove headers/footers
                lines = [line for line in lines if 
                         'Tidningsartiklar - Kandidatuppsats' not in line and
                         not line.startswith('Datum 2026') and
                         not line.startswith('Sida ') and
                         line not in ['Retriever', 'Nyheter']]
                
                # Check if we've hit the end (copyright)
                found_copyright = False
                for line in lines:
                    if ('Optional[©' in line or 
                        'Alla artiklar är skyddade' in line or 
                        'Klicka här för att' in line):
                        found_copyright = True
                        break
                    article_text.append(line)
                
                if found_copyright:
                    break
                
                current_page += 1
                pages_read += 1
            
            # Join article text
            full_article_text = ' '.join(article_text).strip()
            
            # Get URL for this article's starting page
            url = ""
            if page_num in links_by_page and len(links_by_page[page_num]) > 0:
                url = links_by_page[page_num][0]
            
            articles.append({
                'Title': toc_entry['title'],
                'Source': toc_entry['source'],
                'Date': toc_entry['date'],
                'Page': str(toc_entry['page']),
                'Author': author,
                'URL': url,
                'Article_Text': full_article_text[:1000] if len(full_article_text) > 1000 else full_article_text,
                'Full_Text': full_article_text,
                'Has_Text': len(full_article_text) > 0,
                'Text_Length': len(full_article_text),
                'Word_Count': len(full_article_text.split()) if full_article_text else 0
            })
    
    return articles


def main():
    st.set_page_config(page_title="Retriever PDF Parser", page_icon="📰", layout="wide")
    
    st.title("📰 Retriever News Articles PDF Parser")
    st.markdown("Upload a PDF from Retriever database to extract articles into a CSV file")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])
    
    if uploaded_file is not None:
        st.success("✅ PDF file uploaded successfully!")
        
        with st.expander("🔍 Preview raw PDF text (for debugging)"):
            with pdfplumber.open(uploaded_file) as pdf:
                preview_text = ""
                for page in pdf.pages[:2]:
                    preview_text += page.extract_text() + "\n"
            st.text_area("Raw text", preview_text[:3000], height=400)
        
        if st.button("🔍 Parse PDF", type="primary"):
            with st.spinner("Parsing PDF..."):
                try:
                    articles = parse_retriever_pdf(uploaded_file)
                    
                    if articles:
                        df = pd.DataFrame(articles)
                        
                        st.subheader("📊 Extraction Results")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Articles", len(df))
                        with col2:
                            articles_with_text = df['Has_Text'].sum()
                            st.metric("With Text", f"{articles_with_text} / {len(df)}")
                        with col3:
                            articles_with_author = (df['Author'] != '').sum()
                            st.metric("With Author", articles_with_author)
                        with col4:
                            urls_found = (df['URL'] != '').sum()
                            st.metric("URLs Found", urls_found)
                        
                        st.subheader("📋 Article Preview")
                        preview_df = df[['Title', 'Source', 'Date', 'Author', 'Word_Count']].copy()
                        st.dataframe(preview_df, use_container_width=True, height=400)
                        
                        with st.expander("📖 View article details"):
                            if len(df) > 0:
                                sample_titles = [f"{i+1}. {title[:70]}..." if len(title) > 70 else f"{i+1}. {title}" 
                                               for i, title in enumerate(df['Title'])]
                                selected = st.selectbox("Select article", range(len(df)), 
                                                       format_func=lambda x: sample_titles[x])
                                
                                article = df.iloc[selected]
                                
                                st.markdown(f"### {article['Title']}")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.markdown(f"**Source:** {article['Source']}")
                                with col2:
                                    st.markdown(f"**Date:** {article['Date']}")
                                with col3:
                                    st.markdown(f"**Page:** {article['Page']}")
                                
                                if article['Author']:
                                    st.markdown(f"**Author:** {article['Author']}")
                                
                                if article['URL']:
                                    st.markdown(f"**URL:** [{article['URL']}]({article['URL']})")
                                
                                if article['Full_Text']:
                                    st.markdown("**Article Text:**")
                                    st.write(article['Full_Text'])
                                    st.info(f"📏 {article['Text_Length']} characters, {article['Word_Count']} words")
                                else:
                                    st.warning("⚠️ No article text available")
                        
                        st.subheader("💾 Download Options")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            csv_preview = df[['Title', 'Source', 'Date', 'Page', 'Author', 'URL', 'Word_Count', 'Article_Text']].to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                label="📥 CSV (Preview)",
                                data=csv_preview.encode('utf-8-sig'),
                                file_name=f"retriever_articles_preview_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv"
                            )
                        
                        with col2:
                            csv_full = df[['Title', 'Source', 'Date', 'Page', 'Author', 'URL', 'Word_Count', 'Full_Text']].to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                label="📥 CSV (Full Text)",
                                data=csv_full.encode('utf-8-sig'),
                                file_name=f"retriever_articles_full_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv"
                            )
                        
                        with col3:
                            excel_buffer = BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                df[['Title', 'Source', 'Date', 'Page', 'Author', 'URL', 'Word_Count', 'Full_Text']].to_excel(
                                    writer, sheet_name='Articles', index=False
                                )
                            
                            st.download_button(
                                label="📥 Excel File",
                                data=excel_buffer.getvalue(),
                                file_name=f"retriever_articles_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        st.subheader("📊 Articles by Source")
                        source_counts = df['Source'].value_counts().head(15)
                        st.bar_chart(source_counts)
                        
                        st.subheader("📈 Word Count Distribution")
                        st.bar_chart(df['Word_Count'].head(30))
                        
                    else:
                        st.warning("⚠️ No articles were extracted from the PDF.")
                        
                except Exception as e:
                    st.error(f"❌ Error parsing PDF: {str(e)}")
                    st.exception(e)
    
    with st.sidebar:
        st.header("📖 Instructions")
        st.markdown("""
        1. **Upload** your Retriever PDF file
        2. Click **Parse PDF** to extract articles
        3. **Preview** the extracted data
        4. **Download** as CSV or Excel
        
        ### 📊 Extracted Fields:
        - Title (from TOC)
        - Source/Publication
        - Date
        - Page number
        - Author
        - URL (web link)
        - Full article text
        - Word count
        
        ### 💡 Features:
        - Uses table of contents for accurate titles
        - Extracts metadata and article text
        - Handles multi-page articles
        - Links articles to web URLs
        """)
        
        st.header("ℹ️ About")
        st.markdown("""
        This app parses PDF files from the Retriever 
        news database using the table of contents
        for accurate article identification.
        
        **Version:** 7.0 (Simplified, correct structure parsing)
        """)


if __name__ == "__main__":
    main()
