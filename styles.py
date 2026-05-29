def get_stylesheet():
    return """
    /* Main App Background */
    QMainWindow {
        background-color: #08080c;
    }
    
    QWidget {
        color: #e2e2e9;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, sans-serif;
        font-size: 13px;
    }

    /* Scrollbars styling */
    QScrollBar:vertical {
        background-color: #0a0a0f;
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background-color: #242433;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #3b3b54;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    QScrollBar:horizontal {
        background-color: #0a0a0f;
        height: 10px;
        margin: 0px;
        border-radius: 5px;
    }
    QScrollBar::handle:horizontal {
        background-color: #242433;
        min-width: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:horizontal:hover {
        background-color: #3b3b54;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    /* Header Area */
    #HeaderFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #18113c, stop:1 #08080c);
        border-bottom: 2px solid #8b5cf6;
        min-height: 80px;
        border-radius: 8px;
    }
    #AppTitle {
        color: #ffffff;
        font-size: 22px;
        font-weight: 800;
        letter-spacing: 1.5px;
    }
    #AppSubtitle {
        color: #a78bfa;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    /* Left Control Sidebar or Main Input Container */
    #InputPanel {
        background-color: #0f0f18;
        border: 1px solid #1f1f2e;
        border-radius: 12px;
        padding: 14px;
    }
    
    /* Standard Labels */
    QLabel {
        font-weight: 500;
    }
    #SectionTitle {
        font-size: 14px;
        font-weight: 700;
        color: #bf8eff;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Text Edits and Inputs */
    QTextEdit, QLineEdit {
        background-color: #141420;
        border: 1px solid #252538;
        border-radius: 8px;
        padding: 8px;
        color: #f0f0f5;
        selection-background-color: #8b5cf6;
        selection-color: #ffffff;
    }
    QTextEdit:focus, QLineEdit:focus {
        border: 1px solid #a78bfa;
        background-color: #161624;
    }
    QLineEdit::placeholder, QTextEdit::placeholder {
        color: #52526b;
    }

    /* Buttons */
    QPushButton {
        background-color: #7c3aed;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #8b5cf6;
    }
    QPushButton:pressed {
        background-color: #6d28d9;
    }
    QPushButton:disabled {
        background-color: #1f1f2e;
        color: #4e4e63;
    }

    /* Outline / Accent Buttons (Secondary) */
    QPushButton#SecondaryBtn {
        background-color: #161624;
        border: 1px solid #2d2d42;
        color: #e2e2e9;
    }
    QPushButton#SecondaryBtn:hover {
        background-color: #1f1f33;
        border-color: #4c4c6d;
    }
    QPushButton#SecondaryBtn:pressed {
        background-color: #0f0f18;
    }

    /* Success / Green Button */
    QPushButton#SuccessBtn {
        background-color: #059669;
        color: #ffffff;
    }
    QPushButton#SuccessBtn:hover {
        background-color: #10b981;
    }
    QPushButton#SuccessBtn:pressed {
        background-color: #047857;
    }

    /* Danger / Stop / Cancel Button */
    QPushButton#DangerBtn {
        background-color: #dc2626;
        color: #ffffff;
    }
    QPushButton#DangerBtn:hover {
        background-color: #ef4444;
    }
    QPushButton#DangerBtn:pressed {
        background-color: #b91c1c;
    }

    /* Spinboxes / Sliders */
    QSpinBox {
        background-color: #141420;
        border: 1px solid #252538;
        border-radius: 8px;
        padding: 6px;
        color: #ffffff;
        min-width: 60px;
    }
    QSpinBox:focus {
        border: 1px solid #a78bfa;
    }
    
    QSlider::groove:horizontal {
        height: 6px;
        background: #1c1c2b;
        border-radius: 3px;
    }
    QSlider::sub-page:horizontal {
        background: #8b5cf6;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #ffffff;
        width: 16px;
        margin-top: -5px;
        margin-bottom: -5px;
        border-radius: 8px;
        border: 1px solid #8b5cf6;
    }
    QSlider::handle:horizontal:hover {
        background: #bf8eff;
    }

    /* Stats Panel Card */
    #StatsPanel {
        background-color: #0f0f18;
        border: 1px solid #1f1f2e;
        border-radius: 12px;
        padding: 12px;
    }
    #StatValue {
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
    }
    #StatLabel {
        font-size: 11px;
        color: #9e9eb3;
        text-transform: uppercase;
        font-weight: 600;
    }

    /* Queue Container */
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    #QueueViewport {
        background-color: transparent;
    }

    /* Thread Indicator Frame */
    #ThreadGridFrame {
        background-color: #0f0f18;
        border: 1px solid #1f1f2e;
        border-radius: 12px;
        padding: 12px;
    }

    /* Mini Thread Slot Card */
    #ThreadSlot {
        background-color: #141420;
        border: 1px solid #222233;
        border-radius: 6px;
        padding: 6px;
        min-width: 90px;
        max-width: 150px;
    }
    #ThreadSlot[status="Active"] {
        border: 1px solid #8b5cf6;
        background-color: #1a152d;
    }
    #ThreadSlot[status="Idle"] {
        border: 1px solid #222233;
        background-color: #101017;
    }

    /* Progress Bars */
    QProgressBar {
        border: 1px solid #1f1f2e;
        border-radius: 6px;
        text-align: center;
        background-color: #141420;
        height: 18px;
        font-size: 11px;
        font-weight: 700;
        color: #ffffff;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #bf8eff);
        border-radius: 5px;
    }
    
    /* Console Panel */
    #ConsoleLog {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        background-color: #06060a;
        border: 1px solid #151522;
        border-radius: 8px;
        color: #a1a1aa;
    }
    """
