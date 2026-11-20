import requests
import streamlit as st

st.set_page_config(page_title="Knowledge Assistant", page_icon="📚")
st.title("📚 Enterprise Knowledge Assistant")
st.caption("Answers are grounded in approved documents. Open the citations to verify the source passage.")
api_url = st.sidebar.text_input("API URL", "http://127.0.0.1:8000")
retrieval = st.sidebar.selectbox("Retrieval", ["hybrid", "keyword", "semantic"])
question = st.text_area("Ask a question", placeholder="What do the approved documents say?")
if st.button("Search documents", type="primary", disabled=not question.strip()):
    try:
        response = requests.post(f"{api_url.rstrip('/')}/ask", json={"question": question, "retrieval": retrieval}, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result["abstained"]:
            st.warning(result["answer"])
        else:
            st.markdown(result["answer"])
        for citation in result["citations"]:
            page = f", page {citation['page']}" if citation["page"] else ""
            st.caption(f"Source: {citation['source']}{page} · chunk {citation['chunk_id']}")
        with st.expander("Retrieved evidence"):
            for item in result["evidence"]:
                st.markdown(f"**{item['source']} · page {item['page'] or 'n/a'} · score {item['score']:.3f}**")
                st.write(item["text"])
    except requests.RequestException as exc:
        st.error(f"Could not reach the API: {exc}")
