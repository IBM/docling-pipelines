import reflex as rx
from chat_with_file_ingestion.components.chat import chat_interface
from chat_with_file_ingestion.components.sidebar import document_sidebar, log_tearsheet
from chat_with_file_ingestion.states.theme_state import ThemeState
from chat_with_file_ingestion.states.file_state import FileUploadState, LogPollerState
from chat_with_file_ingestion.states.chat_state import ChatState


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
        # Log tearsheet — renders as a fixed overlay on top of everything
        log_tearsheet(),
        rx.el.script("""
            (function() {
            var scrollTimer = null;

            function scrollChat() {
                var c = document.getElementById('chat-body');
                if (!c) return;
                window.requestAnimationFrame(function() {
                c.scrollTop = c.scrollHeight;
                window.requestAnimationFrame(function() {
                    c.scrollTop = c.scrollHeight;
                });
                });
            }

            function debouncedScroll() {
                if (scrollTimer) clearTimeout(scrollTimer);
                scrollTimer = setTimeout(scrollChat, 30);
            }

            function attachObserver() {
                var c = document.getElementById('chat-body');
                if (!c) { setTimeout(attachObserver, 200); return; }
                var obs = new MutationObserver(function(mutations) {
                var hasAddedNodes = mutations.some(function(m) { return m.addedNodes.length > 0; });
                if (hasAddedNodes) { debouncedScroll(); }
                });
                obs.observe(c, { childList: true, subtree: true });
            }

            function scrollLog() {
                var box = document.getElementById('pipeline-log-box');
                if (box) { box.scrollTop = box.scrollHeight; }
            }

            function attachLogObserver() {
                var box = document.getElementById('pipeline-log-box');
                if (!box) { setTimeout(attachLogObserver, 500); return; }
                var logObs = new MutationObserver(function() {
                window.requestAnimationFrame(scrollLog);
                });
                logObs.observe(box, { childList: true, subtree: true });
                // Re-attach after a delay in case the element is replaced by Reflex
                setTimeout(attachLogObserver, 2000);
            }

            function init() {
                attachObserver();
                setTimeout(attachObserver, 1000);
                attachLogObserver();
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', init);
            } else {
                init();
            }
            })();
            """
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
app.add_page(index, route="/", on_load=[FileUploadState.on_load, ChatState.on_load, LogPollerState.clear_logs])