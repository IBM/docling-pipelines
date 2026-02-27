import reflex as rx
from chat_with_file_ingestion.states.chat_state import ChatState
from chat_with_file_ingestion.states.theme_state import ThemeState
from chat_with_file_ingestion.states.file_state import FileUploadState


def theme_toggle() -> rx.Component:
    return rx.el.button(
        rx.cond(
            ThemeState.is_dark_mode,
            rx.icon("sun", class_name="h-5 w-5 text-yellow-400"),
            rx.icon("moon", class_name="h-5 w-5 text-gray-600"),
        ),
        on_click=ThemeState.toggle_theme,
        class_name="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors",
    )


def chat_header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.icon(
                    "bot", class_name="h-6 w-6 text-indigo-600 dark:text-indigo-400"
                ),
                rx.el.h2(
                    "Datasift DocChat",
                    class_name="text-lg font-bold text-gray-800 dark:text-gray-100",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.div(
                rx.cond(
                    FileUploadState.is_uploading,
                    rx.el.div(
                        rx.el.span(
                            "Uploading...",
                            class_name="text-[10px] font-bold text-amber-600 dark:text-amber-400 mr-1 uppercase",
                        ),
                        rx.el.span(
                            class_name="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce"
                        ),
                        rx.el.span(
                            class_name="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:-0.15s]"
                        ),
                        rx.el.span(
                            class_name="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:-0.3s]"
                        ),
                        class_name="flex gap-1 items-center px-3 py-1 bg-amber-50 dark:bg-amber-900/30 rounded-full",
                    ),
                    rx.cond(
                        ChatState.is_processing,
                        rx.el.div(
                            rx.el.span(
                                "Processing...",
                                class_name="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 mr-1 uppercase",
                            ),
                            rx.el.span(
                                class_name="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce"
                            ),
                            rx.el.span(
                                class_name="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s]"
                            ),
                            rx.el.span(
                                class_name="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s]"
                            ),
                            class_name="flex gap-1 items-center px-3 py-1 bg-indigo-50 dark:bg-indigo-900/30 rounded-full",
                        ),
                        rx.el.span(
                            "System Ready",
                            class_name="text-xs font-medium text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/30 px-2 py-1 rounded-full",
                        ),
                    ),
                ),
                theme_toggle(),
                class_name="flex items-center gap-4",
            ),
            class_name="flex items-center justify-between p-4 border-b dark:border-gray-700 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md rounded-t-2xl",
        )
    )


def source_badge(source: str) -> rx.Component:
    return rx.el.span(
        rx.icon("file-text", class_name="h-3 w-3"),
        source,
        class_name="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded text-[10px] font-medium",
    )


def message_bubble(message: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.p(message["content"], class_name="text-sm leading-relaxed"),
                rx.cond(
                    message["sources"].length() > 0,
                    rx.el.div(
                        rx.el.span(
                            "Sources:",
                            class_name="text-[10px] uppercase font-bold text-gray-400 dark:text-gray-500 mb-1 block",
                        ),
                        rx.el.div(
                            rx.foreach(message["sources"], source_badge),
                            class_name="flex flex-wrap gap-1",
                        ),
                        class_name="mt-3 pt-2 border-t border-gray-100 dark:border-gray-700",
                    ),
                ),
                class_name=rx.cond(
                    message["role"] == "user",
                    "bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-3 shadow-sm",
                    "bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-2xl rounded-tl-none px-4 py-3 border border-gray-100 dark:border-gray-700 shadow-sm",
                ),
            ),
            class_name=rx.cond(
                message["role"] == "user", "max-w-[85%] ml-auto", "max-w-[85%] mr-auto"
            ),
        ),
        class_name="w-full flex",
    )


def chat_body() -> rx.Component:
    return rx.el.div(
        rx.cond(
            ChatState.messages.length() == 0,
            rx.el.div(
                rx.icon(
                    "sparkles",
                    class_name="h-12 w-12 text-indigo-100 dark:text-indigo-900 mb-4",
                ),
                rx.el.h3(
                    "Ask anything about your documents",
                    class_name="text-xl font-semibold text-gray-700 dark:text-gray-300",
                ),
                rx.el.p(
                    "I can search through your uploaded files to find answers.",
                    class_name="text-gray-400 dark:text-gray-500 mt-2 text-center max-w-xs",
                ),
                class_name="flex flex-col items-center justify-center h-full opacity-60 py-20",
            ),
            rx.el.div(
                rx.foreach(ChatState.messages, message_bubble), class_name="space-y-6"
            ),
        ),
        class_name="flex-1 overflow-y-auto p-6 scroll-smooth",
    )


def chat_input() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.input(
                    placeholder="Ask a question about your files...",
                    on_change=ChatState.set_user_input,
                    class_name="flex-1 bg-gray-50 dark:bg-gray-800 border-none focus:ring-0 text-sm dark:text-white py-3 px-4 rounded-xl",
                    default_value=ChatState.user_input,
                ),
                rx.el.button(
                    rx.cond(
                        ChatState.is_processing,
                        rx.icon("squirrel", class_name="h-5 w-5 animate-spin"),
                        rx.icon("send", class_name="h-5 w-5"),
                    ),
                    on_click=ChatState.send_message,
                    disabled=ChatState.is_processing,
                    class_name="p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors shadow-md disabled:opacity-50 disabled:cursor-not-allowed",
                ),
                class_name="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 focus-within:border-indigo-300 dark:focus-within:border-indigo-500 transition-all",
            ),
            rx.el.p(
                "Your AI assistant is grounded in the documents provided.",
                class_name="text-[10px] text-center text-gray-400 dark:text-gray-500 mt-2 font-medium",
            ),
            class_name="p-4 bg-white dark:bg-gray-900 rounded-b-2xl border-t dark:border-gray-700 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]",
        )
    )


def chat_interface() -> rx.Component:
    return rx.el.section(
        chat_header(),
        chat_body(),
        chat_input(),
        class_name="flex flex-col h-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden relative",
    )