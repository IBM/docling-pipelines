import reflex as rx
from chat_with_file_ingestion.components.chat import chat_interface
from chat_with_file_ingestion.components.sidebar import document_sidebar
from chat_with_file_ingestion.states.theme_state import ThemeState


def index() -> rx.Component:
    return rx.el.main(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    chat_interface(),
                    class_name="w-full lg:w-[70%] h-[calc(100vh-80px)]",
                ),
                rx.el.div(
                    document_sidebar(),
                    class_name="w-full lg:w-[30%] h-[calc(100vh-80px)]",
                ),
                class_name="flex flex-col lg:flex-row gap-6 max-w-7xl mx-auto w-full px-4",
            ),
            class_name=rx.cond(
                ThemeState.is_dark_mode,
                "min-h-screen bg-gray-950 flex items-center justify-center py-10 transition-colors duration-300",
                "min-h-screen bg-[#F9FAFB] flex items-center justify-center py-10 transition-colors duration-300",
            ),
        ),
        class_name=rx.cond(
            ThemeState.is_dark_mode, "dark font-['Inter']", "font-['Inter']"
        ),
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/")