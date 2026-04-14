import gradio as gr
import time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# --- 1. Configuration (Domain/Settings) ---


class UIConfig(BaseModel):
    """Encapsulates UI constants and specific CSS styling."""

    model_config = ConfigDict(frozen=True)

    APP_TITLE: str = "📄 Datasift DocuChat"
    # Target the button by its specific ID
    # Using a soft 'Light Sky Blue' (#87CEFA) for the 'lite blue' look
    CUSTOM_CSS: str = """
        #build-index-btn {
            background-color: #87CEFA !important;
            color: black !important;
            border: 1px solid #70b8e8 !important;
        }
        #build-index-btn:hover {
            background-color: #b0e2ff !important;
        }
    """
    INDEX_BTN_ID: str = "build-index-btn"


# --- 2. Application Services (Logic Layer) ---


class DocumentService:
    @staticmethod
    def ingest_files(files: Optional[List[gr.File]]) -> str:
        if not files:
            return "No files uploaded."
        file_names = [f.name.split("/")[-1] for f in files]
        time.sleep(1.5)
        return f"Successfully indexed: {', '.join(file_names)}"

    @staticmethod
    def get_model_response(message: str, history: List[List[str]]) -> str:
        time.sleep(1)
        return f"I've analyzed your documents. This is a placeholder response for: '{message}'"


# --- 3. Presentation Layer (Gradio UI) ---


def create_app() -> gr.Blocks:
    config = UIConfig()
    service = DocumentService()

    # Pass the CSS directly to the Blocks constructor
    with gr.Blocks(title="Datasift DocuChat", css=config.CUSTOM_CSS) as demo:
        gr.Markdown(f"# {config.APP_TITLE}")
        gr.Markdown("Upload your documents on the left and ask questions on the right.")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 1. Upload Knowledge Base")
                file_input = gr.File(label="Upload files", file_count="multiple")

                # Assign the specific elem_id here
                upload_button = gr.Button(
                    "Build Index", variant="primary", elem_id=config.INDEX_BTN_ID
                )

                status_output = gr.Textbox(
                    label="System Status", placeholder="Waiting..."
                )

            with gr.Column(scale=2):
                gr.Markdown("### 2. Chat with your Docs")
                chatbot = gr.Chatbot(height=500)
                msg = gr.Textbox(label="Ask a question", placeholder="Type here...")
                _ = gr.ClearButton([msg, chatbot])

        # Event Handling
        upload_button.click(
            fn=service.ingest_files, inputs=[file_input], outputs=[status_output]
        )
        msg.submit(
            fn=service.get_model_response, inputs=[msg, chatbot], outputs=[chatbot]
        ).then(lambda: "", None, [msg])

    return demo


if __name__ == "__main__":
    create_app().launch()
