import threading
import gradio as gr

def run_bot():
    print("🚀 7anime Bot Starting...")
    app.run()

# Gradio interface taaki Hugging Face space active rahe
def dummy_interface(name):
    return f"Hello {name}, 7anime Cloud Bot is running smoothly!"

demo = gr.Interface(
    fn=dummy_interface,
    inputs="text",
    outputs="text",
    title="7anime Cloud Vidhide Bot Dashboard",
    description="Bot is running in the background. Send videos via Telegram!"
)

if __name__ == "__main__":
    # Bot ko background thread mein chalao
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Gradio web server launch karo
    demo.launch(server_name="0.0.0.0", server_port=7860)

