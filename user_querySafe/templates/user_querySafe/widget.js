(function() {
    // Load external scripts (Marked.js and DOMPurify)
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = () => {
                console.error('Failed to load ' + src);
                resolve(); // Continue even if load fails
            };
            document.head.appendChild(script);
        });
    }

    function loadDependencies(callback) {
        const loads = [];
        if (!window.marked) {
            loads.push(loadScript('https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js'));
        }
        if (!window.DOMPurify) {
            loads.push(loadScript('https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js'));
        }
        Promise.all(loads).then(callback);
    }

    // Initialize widget after dependencies are loaded
    loadDependencies(() => {
        const config = {
            chatbotName: '{{ chatbot_name|escapejs }}',
            chatbotLogo: '{{ chatbot_logo|escapejs }}',
            baseUrl: '{{ base_url|escapejs }}'
        };

        // Inject CSS styles
        const styles = `
            /* Isolate chatbot from external styles */
            #mv-chatbot-widget-root,
            #mv-chatbot-widget-root * {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif !important;
                line-height: 20px;
                box-sizing: border-box !important;
            }

            /* Override any Bootstrap classes that might affect our elements */
            #mv-chatbot-widget-root .btn,
            #mv-chatbot-widget-root .form-control,
            #mv-chatbot-widget-root .container,
            #mv-chatbot-widget-root .row,
            #mv-chatbot-widget-root .col {
                all: unset !important;
                width: auto !important;
                height: auto !important;
                margin: 0 !important;
                padding: 0 !important;
                border: none !important;
                background: none !important;
            }

            #mv-chatbot-widget-root {
                z-index: 99999;
            }

            #mv-chatbot-fab {
                position: fixed;
                right: 32px;
                bottom: 32px;
                background: #290a4e;
                border-radius: 50%;
                width: 56px;
                height: 56px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.18);
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: box-shadow 0.2s;
                z-index: 99999;
            }

            #mv-chatbot-fab:hover {
                box-shadow: 0 8px 24px rgba(0,123,255,0.18);
                background: rgb(59, 13, 116);
            }

            #mv-chatbot-modal {
                position: fixed;
                right: 10px;
                bottom: 100px;
                width: 370px;
                max-width: 95vw;
                height: 620px;
                background: #fff;
                border-radius: 10px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.18);
                display: flex;
                flex-direction: column;
                z-index: 99999;
                overflow: hidden;
                animation: mv-chatbot-fadein 0.2s;
                border: 1px solid rgb(196, 196, 196);
            }
            p{
                margin-bottom: 0px;
            }

            @keyframes mv-chatbot-fadein {
                from { opacity: 0; transform: translateY(40px); }
                to { opacity: 1; transform: translateY(0); }
            }

            #mv-chatbot-header {
                background: #eaeaea;
                color: #1c1c1c;
                padding: 12px 18px 12px 14px;
                font-size: 1.2rem;
                font-weight: 600;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid #e0e0e0;
                min-height: 60px;
            }

            .header-left {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .logo-icon {
                width: 38px;
                height: 38px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #fff;
                border-radius: 50%;
                box-shadow: 0 2px 8px rgba(0,123,255,0.07);
                overflow: hidden;
            }

            .logo-icon img {
                border: 3px solid white;
                width: 100%;
                height: 100%;
                object-fit: cover;
                object-position: center;
                border-radius: 50%;
                display: block;
            }

            .header-title {
                display: flex;
                flex-direction: column;
                justify-content: center;
            }

            .main-title {
                font-size: 1.08rem;
                font-weight: 700;
                color: #222;
                margin-bottom: 2px;
                letter-spacing: 0.2px;
            }

            .sub-title {
                font-size: 0.93rem;
                color: #555;
                font-weight: 300;
                letter-spacing: 0.1px;
            }

            #mv-chatbot-close {
                background: none;
                border: none;
                padding: 4px;
                margin-left: 8px;
                cursor: pointer;
                border-radius: 50%;
                transition: background 0.18s;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            #mv-chatbot-close:hover {
                background: #e0eaff;
            }

            #mv-chatbot-messages {
                flex: 1;
                overflow-y: auto;
                padding: 18px 10px 10px 10px;
                background: #f4f4f4;
                display: flex;
                flex-direction: column;
                scrollbar-width: thin;
                scrollbar-color: #cecece #e0e0e000;
            }

            #mv-chatbot-messages::-webkit-scrollbar {
                width: 8px;
                border-radius: 8px;
                background: #e0e0e0;
            }

            #mv-chatbot-messages::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, #007bff 40%, #0056b3 100%);
                border-radius: 8px;
            }

            .mv-chatbot-message {
                margin-bottom: 15px;
                max-width: 75%;
                padding: 12px 16px;
                border-radius: 16px;
                word-wrap: break-word;
                font-size: 1rem;
                padding-bottom: 10px;
            }

            .mv-chatbot-message p {
                margin: 0px;
            }

            .mv-chatbot-user-msg {
                background-color: #1c1c1c;
                color: white;
                align-self: flex-end;
                border-bottom-right-radius: 0;
                text-align: right;
            }

            .mv-chatbot-bot-msg {
                background-color: #cbcbcb;
                align-self: flex-start;
                border-bottom-left-radius: 0;
            }

            #mv-chatbot-input-bar {
                display: flex;
                background-color: white;
                border-top: 1px solid #d3d3d3;
                flex-direction: row;
                border-radius: 0 0 18px 18px;
                align-items: center;
                padding: 10px;
                gap: 8px;
            }

            #mv-chatbot-user-input {
                flex: 1;
                padding: 12px 14px;
                border-radius: 10px;
                border: none;
                font-size: 1rem;
                min-height: 44px;
                max-height: 120px;
                resize: vertical;
                background: #ffffff00;
                transition: border-color 0.2s, box-shadow 0.2s;
                outline: none;
                font-family: Arial, Helvetica, sans-serif;
            }

            #mv-chatbot-send-btn {
                background-color: #2a2a2a;
                color: white;
                padding: 10px 14px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 1rem;
                font-weight: 500;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            #mv-chatbot-send-btn:hover {
                background-color: #0056b3;
            }

            #mv-chatbot-send-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            .mv-typing-indicator {
                display: flex;
                align-items: center;
                gap: 2px;
                font-style: italic;
                font-size: 0.98em;
                color: #393939;
                padding: 8px 12px;
                background: rgb(255, 255, 255);
                border-radius: 12px;
                margin: 8px 0;
                width: fit-content;
            }

            .mv-typing-indicator .dot {
                height: 8px;
                width: 8px;
                margin: 0 2px;
                background-color: rgb(103, 103, 103);
                border-radius: 50%;
                display: inline-block;
                animation: bounce 1.2s infinite both;
            }

            .mv-typing-indicator .dot:nth-child(1) { animation-delay: 0s; }
            .mv-typing-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
            .mv-typing-indicator .dot:nth-child(3) { animation-delay: 0.4s; }

            @keyframes bounce {
                0%, 80%, 100% { transform: translateY(0); }
                40% { transform: translateY(-8px); }
            }

            .devlop-credit {
                font-size: 10px;
                text-align: center;
                padding-bottom: 2px;
            }

            .mv-chatbot-note {
                font-size: 10px;
                color: #888;
                text-align: center;
                margin: 4px 0 8px 0;
                padding: 0 10px;
                line-height: 1.4;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 4px;
            }

            /* Feedback modal styles */
            .mv-feedback-backdrop {
                position: absolute;
                top: 62px;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.32);
                z-index: 10010;
                display: block;
                border-radius: 0 0 10px 10px;
            }
            .mv-feedback-panel {
                position: absolute;
                left: 50%;
                bottom: 18px;
                transform: translateX(-50%);
                width: calc(100% - 56px);
                max-width: 360px;
                z-index: 10011;
                background: #fff;
                padding: 12px;
                border-radius: 10px;
                box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif !important;
            }
            .mv-feedback-panel .mv-feedback-header {
                margin-bottom: 12px;
            }
            .mv-feedback-panel .mv-feedback-header h4 {
                margin: 0 !important;
                font-size: 1rem !important;
                font-weight: 600 !important;
                color: #222 !important;
            }
            .mv-feedback-panel .mv-feedback-header small {
                display: block;
                color: #777 !important;
                font-size: 0.85rem !important;
                font-weight: 400 !important;
                margin-top: 2px !important;
            }
            .mv-feedback-panel .mv-feedback-stars {
                text-align: center !important;
                margin: 12px 0 !important;
                font-size: 1.6rem !important;
            }
            .mv-feedback-panel .mv-feedback-star {
                cursor: pointer !important;
                color: #bdbdbd !important;
                padding: 0 6px !important;
                font-size: 1.6rem !important;
                transition: color 0.2s !important;
                display: inline-block !important;
            }
            .mv-feedback-panel .mv-feedback-star:hover {
                color: #f5b301 !important;
            }
            .mv-feedback-panel .mv-feedback-star.active {
                color: #f5b301 !important;
            }
            .mv-feedback-panel textarea {
                box-sizing: border-box !important;
                width: 100% !important;
                max-height: 160px !important;
                min-height: 80px !important;
                overflow: auto !important;
                padding: 10px !important;
                border-radius: 8px !important;
                border: 1px solid #e0e0e0 !important;
                resize: vertical !important;
                font-family: Arial, Helvetica, sans-serif !important;
                font-size: 0.9rem !important;
                line-height: 1.4 !important;
                margin: 12px 0 !important;
                color: #333 !important;
                background: #fff !important;
            }
            .mv-feedback-panel textarea::placeholder {
                color: #bbb !important;
            }
            .mv-feedback-panel .btn {
                padding: 6px 10px !important;
                border-radius: 6px !important;
                border: none !important;
                cursor: pointer !important;
                font-size: 0.9rem !important;
                font-weight: 500 !important;
                margin: 0 !important;
                outline: none !important;
                transition: opacity 0.2s !important;
            }
            .mv-feedback-panel .text-muted {
                color: #777 !important;
            }
            .mv-feedback-panel .btn-primary {
                background: linear-gradient(90deg, #5b25a6 0%, #3b0d74 100%) !important;
                color: #fff !important;
            }
            .mv-feedback-panel .btn-primary:hover {
                opacity: 0.95 !important;
            }
            .mv-feedback-panel .btn-secondary {
                background: none !important;
                color: #222 !important;
                border: none !important;
            }
            .mv-feedback-panel .btn-secondary:hover {
                opacity: 0.7 !important;
            }
            #mv-feedback-content {
                display: block !important;
            }
        `;

        // Create and inject style element
        const styleEl = document.createElement('style');
        styleEl.textContent = styles;
        document.head.appendChild(styleEl);

        // Create widget HTML structure
        const widgetHtml = `
            <div id="mv-chatbot-widget-root">
                <div id="mv-chatbot-fab" onclick="querySafe.toggleWidget()">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="#fff">
                        <circle cx="12" cy="12" r="12" fill="#4b1a86"/>
                        <path d="M7 17v-2a4 4 0 0 1 4-4h2a4 4 0 0 1 4 4v2" stroke="#fff" stroke-width="2" fill="none"/>
                        <circle cx="9" cy="10" r="1" fill="#fff"/>
                        <circle cx="15" cy="10" r="1" fill="#fff"/>
                    </svg>
                </div>
                <div id="mv-chatbot-modal">
                    <div id="mv-chatbot-header">
                        <div class="header-left">
                            <div class="logo-icon">
                                ${config.chatbotLogo ? 
                                    `<img src="${config.chatbotLogo}" alt="${config.chatbotName}" width="32" height="32">` :
                                    `<svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                                        <circle cx="16" cy="16" r="16" fill="#4b1a86"/>
                                        <text x="16" y="21" text-anchor="middle" font-size="16" fill="#fff" font-family="Segoe UI, Arial" font-weight="bold">${config.chatbotName.slice(0,2)}</text>
                                    </svg>`
                                }
                            </div>
                            <div class="header-title">
                                <div class="main-title">${config.chatbotName}</div>
                                <div class="sub-title">AI Powered Support Agent</div>
                            </div>
                        </div>
                        <button id="mv-chatbot-close" onclick="querySafe.toggleWidget()" title="Close">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                                <circle cx="12" cy="12" r="12" fill="#f4f4f4"/>
                                <path d="M8 8l8 8M16 8l-8 8" stroke="#191919" stroke-width="2" stroke-linecap="round"/>
                            </svg>
                        </button>
                    </div>
                    <div id="mv-chatbot-messages"></div>
                    <div id="mv-chatbot-input-bar">
                        <textarea id="mv-chatbot-user-input" placeholder="Type your message..." rows="2"></textarea>
                        <button id="mv-chatbot-send-btn" title="Send">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff">
                                <path d="M2 21l21-9-21-9v7l15 2-15 2z" fill="#fff"/>
                            </svg>
                        </button>
                    </div>
                    <div id="mv-feedback-modal" style="display:none;">
                        <div class="mv-feedback-backdrop"></div>
                        <div class="mv-feedback-panel">
                            <div class="mv-feedback-header">
                                <h4 style="margin:0;font-size:1rem;">Quick feedback</h4>
                                <small class="text-muted">Help us improve this chat</small>
                            </div>
                            <div id="mv-feedback-content">
                                <div style="text-align:center;margin:12px 0;">
                                    <div class="mv-feedback-stars" style="font-size:1.6rem;">
                                        <span class="mv-feedback-star" data-value="1">☆</span>
                                        <span class="mv-feedback-star" data-value="2">☆</span>
                                        <span class="mv-feedback-star" data-value="3">☆</span>
                                        <span class="mv-feedback-star" data-value="4">☆</span>
                                        <span class="mv-feedback-star" data-value="5">☆</span>
                                    </div>
                                    <div style="display:none;">
                                        <input type="radio" name="rating" value="1">
                                        <input type="radio" name="rating" value="2">
                                        <input type="radio" name="rating" value="3">
                                        <input type="radio" name="rating" value="4">
                                        <input type="radio" name="rating" value="5">
                                    </div>
                                </div>
                                <textarea id="mv-feedback-text" placeholder="Any suggestions? (optional)"></textarea>
                                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:10px;">
                                    <button class="mv-feedback-skip btn btn-secondary" type="button">Skip</button>
                                    <button class="mv-feedback-submit btn btn-primary" type="button">Submit</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="devlop-credit">Made with ❤ by Metric Vibes</div>
                    <div class="mv-chatbot-note">
                        <span>
                            <b>NOTE:</b> This is AI and may make mistakes. Please check answers carefully. Conversations are stored for overview and training purposes.
                        </span>
                    </div>
                </div>
            </div>
        `;

        // Create global namespace for widget
        window.querySafe = {
            config: config,
            chatHistory: [],
            isOpen: false,
            conversationId: null,
            greetingSent: false,
            waiting: false,
            sessionStartTime: null,
            userMessageCount: 0,
            feedbackMinMs: 2 * 3 * 1000, // 2 minutes
            feedbackMinMsgs: 3,
            feedbackShown: false,

            init: function() {
                const container = document.createElement('div');
                container.innerHTML = widgetHtml;
                document.body.appendChild(container);
                this.bindEvents();
                
                // Initialize modal state
                const modal = document.getElementById('mv-chatbot-modal');
                modal.style.display = 'none';
            },

            bindEvents: function() {
                const input = document.getElementById('mv-chatbot-user-input');
                const sendBtn = document.getElementById('mv-chatbot-send-btn');
                const self = this;

                // Send button click
                sendBtn.addEventListener('click', function() {
                    if (sendBtn.disabled) return;
                    const message = input.value.trim();
                    if (message) {
                        self.sendMessage(message);
                        input.value = '';
                        input.style.height = 'auto';
                    }
                });

                // Enter key (send only if not waiting)
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        if (sendBtn.disabled) {
                            e.preventDefault();
                            return;
                        }
                        e.preventDefault();
                        const message = input.value.trim();
                        if (message) {
                            self.sendMessage(message);
                            input.value = '';
                            input.style.height = 'auto';
                        }
                    }
                });

                // Auto resize textarea
                input.addEventListener('input', function() {
                    input.style.height = 'auto';
                    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
                });

                // Feedback modal event handlers
                document.addEventListener('click', (e) => {
                    // Star click
                    if (e.target && e.target.classList && e.target.classList.contains('mv-feedback-star')) {
                        const val = parseInt(e.target.getAttribute('data-value') || '0');
                        document.querySelectorAll('.mv-feedback-star').forEach(s => s.classList.remove('active'));
                        for (let i = 1; i <= val; i++) {
                            const s = document.querySelector('.mv-feedback-star[data-value="' + i + '"]');
                            if (s) s.classList.add('active');
                        }
                        const radio = document.querySelector('#mv-feedback-modal input[name="rating"][value="' + val + '"]');
                        if (radio) radio.checked = true;
                    }

                    // Skip button
                    if (e.target && e.target.classList && e.target.classList.contains('mv-feedback-skip')) {
                        self.hideFeedbackModal();
                    }

                    // Submit button
                    if (e.target && e.target.classList && e.target.classList.contains('mv-feedback-submit')) {
                        const ratingEl = document.querySelector('#mv-feedback-modal input[name="rating"]:checked');
                        const rating = ratingEl ? parseInt(ratingEl.value) : 0;
                        const text = document.getElementById('mv-feedback-text').value || '';

                        // Show local thank you
                        const content = document.getElementById('mv-feedback-content');
                        content.innerHTML = '<div style="padding:18px;text-align:center;"><h4 style="margin:0 0 6px;">Thanks for your feedback!</h4><p style="margin:0;color:#666;font-size:0.95rem;">We appreciate the time you took to help us improve.</p></div>';
                        self.feedbackShown = true;

                        // Send to server
                        if (typeof self.conversationId !== 'undefined' && self.conversationId) {
                            fetch(self.config.baseUrl + '/chat/feedback/', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ conversation_id: self.conversationId, rating: rating, description: text })
                            })
                            .then(res => res.json())
                            .then(data => {
                                if (data && data.success) {
                                    console.log('Feedback submitted', data);
                                } else {
                                    console.warn('Feedback submission error', data);
                                }
                            })
                            .catch(err => {
                                console.error('Feedback submit failed', err);
                            });
                        } else {
                            console.warn('No conversation id available; feedback not sent to server.');
                        }

                        setTimeout(() => { self.hideFeedbackModal(); }, 1000);
                    }
                });
            },

            toggleWidget: function() {
                const modal = document.getElementById('mv-chatbot-modal');
                this.isOpen = !this.isOpen;
                
                if (!this.isOpen) {
                    // Check if feedback modal should be shown
                    try {
                        const now = Date.now();
                        const duration = this.sessionStartTime ? (now - this.sessionStartTime) : 0;
                        if (duration >= this.feedbackMinMs && this.userMessageCount >= this.feedbackMinMsgs && !this.feedbackShown) {
                            this.showFeedbackModal();
                            return;
                        }
                    } catch(e) {
                        console.warn('feedback check error', e);
                    }
                    modal.style.display = 'none';
                } else {
                    modal.style.display = 'flex';
                    if (!this.sessionStartTime) this.sessionStartTime = Date.now();
                    if (!this.greetingSent) {
                        this.displayMessage('Hi! How can I help you today?', false);
                        this.greetingSent = true;
                    }
                    document.getElementById('mv-chatbot-user-input').focus();
                }
            },

            showFeedbackModal: function() {
                const m = document.getElementById('mv-feedback-modal');
                if (!m) return;
                m.style.display = 'block';
            },

            hideFeedbackModal: function() {
                const m = document.getElementById('mv-feedback-modal');
                if (!m) return;
                m.style.display = 'none';
                // Then close the widget
                document.getElementById('mv-chatbot-modal').style.display = 'none';
                this.isOpen = false;
            },

            displayMessage: function(message, isUser) {
                const messagesDiv = document.getElementById('mv-chatbot-messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `mv-chatbot-message ${isUser ? 'mv-chatbot-user-msg' : 'mv-chatbot-bot-msg'}`;

                // Format message with markdown (sanitized)
                if (isUser) {
                    // User messages: always use textContent (no HTML)
                    messageDiv.textContent = message;
                } else if (window.marked) {
                    try {
                        marked.setOptions({
                            breaks: true,
                            gfm: true,
                            headerIds: false,
                            mangle: false
                        });
                        const rawHtml = marked.parse(message);
                        // Sanitize HTML to prevent XSS from bot responses
                        messageDiv.innerHTML = window.DOMPurify ? DOMPurify.sanitize(rawHtml) : rawHtml.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/on\w+="[^"]*"/gi, '');
                    } catch (error) {
                        messageDiv.textContent = message;
                    }
                } else {
                    messageDiv.textContent = message;
                }

                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTo({
                    top: messagesDiv.scrollHeight,
                    behavior: 'smooth'
                });
            },

            showTypingIndicator: function() {
                const messagesDiv = document.getElementById('mv-chatbot-messages');
                const typingDiv = document.createElement('div');
                typingDiv.id = 'mv-typing-indicator';
                typingDiv.className = 'mv-typing-indicator';
                typingDiv.innerHTML = `
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span style="margin-left:8px;"></span>
                `;
                messagesDiv.appendChild(typingDiv);
                messagesDiv.scrollTo({
                    top: messagesDiv.scrollHeight,
                    behavior: 'smooth'
                });
            },

            removeTypingIndicator: function() {
                const typingDiv = document.getElementById('mv-typing-indicator');
                if (typingDiv) typingDiv.remove();
            },

            setInputEnabled: function(enabled) {
                const sendBtn = document.getElementById('mv-chatbot-send-btn');
                sendBtn.disabled = !enabled;
            },

            sendMessage: function(message) {
                if (this.waiting) return;
                this.waiting = true;
                this.setInputEnabled(false);

                // Track session and message count
                if (!this.sessionStartTime) this.sessionStartTime = Date.now();
                this.userMessageCount++;

                this.displayMessage(message, true);
                this.showTypingIndicator();

                fetch(`${this.config.baseUrl}/chat/`, {
                    method: 'POST',
                    mode: 'cors',
                    credentials: 'omit',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        query: message,
                        chatbot_id: '{{ chatbot.chatbot_id }}',
                        conversation_id: this.conversationId
                    })
                })
                .then(response => {
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    return response.json();
                })
                .then(data => {
                    this.removeTypingIndicator();
                    if (data.error) throw new Error(data.error);
                    if (data.conversation_id) this.conversationId = data.conversation_id;
                    if (data.answer) this.displayMessage(data.answer, false);
                })
                .catch(error => {
                    this.removeTypingIndicator();
                    this.displayMessage('Sorry, something went wrong. Please try again.', false);
                })
                .finally(() => {
                    this.waiting = false;
                    this.setInputEnabled(true);
                });
            }
        };

        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => querySafe.init());
        } else {
            querySafe.init();
        }
    });
})();