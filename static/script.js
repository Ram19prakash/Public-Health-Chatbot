class MedicalChatbot {
    constructor() {
        this.currentDepartment = null;
        this.currentQuestion = null;
        this.selectedOptions = [];
        this.answerHistory = [];
        this.currentStep = 0;
        this.currentLanguage = 'en';
        
        this.initializeEventListeners();
        this.ensureScrollability();
        this.loadCurrentLanguage();
    }

    initializeEventListeners() {
        // Department selection
        document.querySelectorAll('.department-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.selectDepartment(e.target.dataset.department);
            });
        });

        // Navigation buttons
        document.getElementById('nextButton').addEventListener('click', () => this.nextStep());
        document.getElementById('prevButton').addEventListener('click', () => this.previousStep());
        
        // Control buttons
        document.getElementById('restartChat').addEventListener('click', () => this.restartChat());
        document.getElementById('newConsultation').addEventListener('click', () => this.restartChat());
        
        // Language selector
        document.getElementById('languageSelect').addEventListener('change', (e) => {
            this.setLanguage(e.target.value);
        });
    }

    ensureScrollability() {
        // Make sure the chat messages area is scrollable
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.style.overflowY = 'auto';
            chatMessages.style.minHeight = '0';
        }
    }

    async loadCurrentLanguage() {
        try {
            const response = await fetch('/api/get_current_language');
            const data = await response.json();
            this.currentLanguage = data.language;
            document.getElementById('languageSelect').value = this.currentLanguage;
            document.getElementById('currentLanguage').textContent = data.language_name;
        } catch (error) {
            console.error('Error loading language:', error);
        }
    }

    async setLanguage(language) {
        try {
            const response = await fetch('/api/set_language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ language: language })
            });

            const data = await response.json();
            if (data.success) {
                this.currentLanguage = language;
                document.getElementById('currentLanguage').textContent = data.message.split(' ').pop();
                
                // Show success message
                this.addMessage('bot', `Language changed to ${data.message.split(' ').pop()}`);
                
                // Restart chat if in progress
                if (this.currentDepartment) {
                    await this.restartChat();
                    await this.selectDepartment(this.currentDepartment);
                }
            }
        } catch (error) {
            console.error('Error setting language:', error);
            this.addMessage('bot', 'Error changing language. Please try again.');
        }
    }

    async selectDepartment(department) {
        this.currentDepartment = department;
        
        // Update UI - highlight selected department
        document.querySelectorAll('.department-btn').forEach(btn => {
            btn.classList.remove('selected', 'department-highlight');
        });
        event.target.classList.add('selected', 'department-highlight');
        
        // Update department in chat header
        document.getElementById('currentDepartment').textContent = 
            document.querySelector(`[data-department="${department}"]`).textContent;
        
        // Show question section, hide department selection
        document.getElementById('departmentSection').style.display = 'none';
        document.getElementById('questionSection').style.display = 'flex';
        document.getElementById('resultsSection').style.display = 'none';
        
        // Start the chat
        await this.startChat(department);
        
        // Ensure scrollability after content loads
        setTimeout(() => this.ensureScrollability(), 100);
    }

    async startChat(department) {
        try {
            // Add welcome message for the department
            this.addMessage('bot', `Starting ${this.getDepartmentName(department)} assessment. Please answer the following questions about your symptoms.`);
            
            const response = await fetch('/api/start_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    department: department,
                    language: this.currentLanguage
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.addMessage('bot', data.message);
                this.currentQuestion = data.question;
                this.displayQuestion(data.question);
                this.updateProgress();
                
                // Show navigation buttons
                document.getElementById('prevButton').style.display = 'none';
                document.getElementById('nextButton').style.display = 'block';
                document.getElementById('nextButton').disabled = true;
            }
        } catch (error) {
            console.error('Error starting chat:', error);
            this.addMessage('bot', 'Sorry, I encountered an error. Please try again.');
        }
    }

    displayQuestion(question) {
        const questionDisplay = document.getElementById('questionDisplay');
        
        let html = `<div class="current-question">${question.question}</div>`;
        html += `<div class="options-container">`;
        
        if (question.type === 'single_choice' || question.type === 'treatment_selection') {
            question.options.forEach(option => {
                html += `
                    <div class="option-item ${question.type === 'treatment_selection' ? 'treatment-option' : ''}" data-value="${option.value}">
                        ${option.text}
                    </div>
                `;
            });
        } else if (question.type === 'multiple_choice') {
            question.options.forEach(option => {
                html += `
                    <div class="option-item multiple-option" data-value="${option.value}">
                        <input type="checkbox" id="opt_${option.value}">
                        <label for="opt_${option.value}">${option.text}</label>
                    </div>
                `;
            });
        }
        
        html += `</div>`;
        questionDisplay.innerHTML = html;
        
        // Add event listeners to options
        if (question.type === 'single_choice' || question.type === 'treatment_selection') {
            document.querySelectorAll('.option-item:not(.multiple-option)').forEach(item => {
                item.addEventListener('click', () => {
                    document.querySelectorAll('.option-item:not(.multiple-option)').forEach(i => i.classList.remove('selected'));
                    item.classList.add('selected');
                    this.selectedOptions = [item.dataset.value];
                    document.getElementById('nextButton').disabled = false;
                });
            });
        } else if (question.type === 'multiple_choice') {
            document.querySelectorAll('.multiple-option input[type="checkbox"]').forEach(checkbox => {
                checkbox.addEventListener('change', () => {
                    this.updateMultipleSelection();
                });
            });
        }
        
        // Add question to chat
        this.addMessage('bot', question.question, 'question-message');
        
        // Ensure scroll to bottom
        this.scrollToBottom();
    }

    updateMultipleSelection() {
        const selectedCheckboxes = document.querySelectorAll('.multiple-option input[type="checkbox"]:checked');
        this.selectedOptions = Array.from(selectedCheckboxes).map(cb => cb.id.replace('opt_', ''));
        document.getElementById('nextButton').disabled = this.selectedOptions.length === 0;
    }

    async nextStep() {
        if (!this.currentQuestion || this.selectedOptions.length === 0) {
            console.log('Cannot proceed: no question or selection');
            return;
        }
        
        // Store the answer
        const answer = this.currentQuestion.type === 'multiple_choice' ? this.selectedOptions : this.selectedOptions[0];
        this.answerHistory.push({
            question: this.currentQuestion,
            answer: answer
        });
        
        // Add user's answer to chat
        const answerText = Array.isArray(answer) ? answer.join(', ') : answer;
        this.addMessage('user', answerText);
        
        // Process the answer
        if (this.currentQuestion.id === 'treatment_preference') {
            await this.getTreatmentRecommendations(answer);
            return;
        }
        
        try {
            const response = await fetch('/api/answer_question', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question_id: this.currentQuestion.id,
                    answer: answer
                })
            });

            const data = await response.json();
            
            if (data.next_question) {
                this.currentQuestion = data.next_question;
                this.displayQuestion(data.next_question);
                this.currentStep++;
                this.updateProgress();
                
                // Show previous button after first question
                if (this.answerHistory.length > 0) {
                    document.getElementById('prevButton').style.display = 'block';
                }
            } else {
                console.log('No next question received');
            }
            
            // Reset for next question
            this.selectedOptions = [];
            document.getElementById('nextButton').disabled = true;
            
        } catch (error) {
            console.error('Error processing answer:', error);
            this.addMessage('bot', 'Sorry, I encountered an error. Please try again.');
        }
    }

    previousStep() {
        if (this.answerHistory.length === 0) {
            console.log('No history to go back to');
            return;
        }
        
        // Remove last answer
        const lastAnswer = this.answerHistory.pop();
        this.currentQuestion = lastAnswer.question;
        
        // Remove the last user and bot messages
        const chatMessages = document.getElementById('chatMessages');
        const messages = chatMessages.querySelectorAll('.message');
        if (messages.length >= 2) {
            chatMessages.removeChild(messages[messages.length - 1]); // Remove user answer
            chatMessages.removeChild(messages[messages.length - 2]); // Remove bot question
        }
        
        // Redisplay the question
        this.displayQuestion(this.currentQuestion);
        this.currentStep--;
        this.updateProgress();
        
        // Restore previous selection
        if (this.currentQuestion.type === 'single_choice') {
            const option = document.querySelector(`[data-value="${lastAnswer.answer}"]`);
            if (option) {
                option.classList.add('selected');
                this.selectedOptions = [lastAnswer.answer];
                document.getElementById('nextButton').disabled = false;
            }
        } else if (this.currentQuestion.type === 'multiple_choice') {
            // For multiple choice, restore all checked boxes
            lastAnswer.answer.forEach(answerValue => {
                const checkbox = document.getElementById(`opt_${answerValue}`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });
            this.selectedOptions = lastAnswer.answer;
            document.getElementById('nextButton').disabled = this.selectedOptions.length === 0;
        }
        
        // Hide previous button if we're at the first question
        if (this.answerHistory.length === 0) {
            document.getElementById('prevButton').style.display = 'none';
        }
        
        this.scrollToBottom();
    }

    async getTreatmentRecommendations(treatmentType) {
        try {
            this.addMessage('bot', 'Getting your personalized treatment recommendations...');
            
            const response = await fetch('/api/select_treatment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    treatment_type: treatmentType
                })
            });

            const data = await response.json();
            
            // Remove the "getting recommendations" message
            const chatMessages = document.getElementById('chatMessages');
            const messages = chatMessages.querySelectorAll('.message');
            if (messages.length > 0) {
                chatMessages.removeChild(messages[messages.length - 1]);
            }
            
            // Hide question section, show results
            document.getElementById('questionSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'block';
            
            // Show results in chat
            if (data.requires_doctor) {
                this.addMessage('bot', data.formatted_message || data.message, 'treatment-message warning-message');
            } else {
                this.addMessage('bot', data.formatted_message || data.message, 'treatment-message');
            }
            
            this.scrollToBottom();
            
        } catch (error) {
            console.error('Error getting treatments:', error);
            this.addMessage('bot', 'Sorry, I encountered an error getting treatment recommendations.');
        }
    }

    addMessage(sender, message, messageClass = '') {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message ${messageClass}`;
        
        // Format message with basic markdown
        let formattedMessage = message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        
        messageDiv.innerHTML = formattedMessage;
        chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    scrollToBottom() {
        const chatMessages = document.getElementById('chatMessages');
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }

    updateProgress() {
        const progressText = document.getElementById('progressText');
        if (this.currentQuestion && this.currentQuestion.id === 'treatment_preference') {
            progressText.textContent = 'Final Step';
        } else {
            progressText.textContent = `Step ${this.currentStep + 1}`;
        }
    }

    getDepartmentName(departmentKey) {
        const btn = document.querySelector(`[data-department="${departmentKey}"]`);
        return btn ? btn.textContent : departmentKey;
    }

    async restartChat() {
        try {
            await fetch('/api/restart_chat', { method: 'POST' });
            
            // Reset UI
            document.getElementById('departmentSection').style.display = 'block';
            document.getElementById('questionSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'none';
            
            // Clear chat
            document.getElementById('chatMessages').innerHTML = '<div class="message bot-message">👋 Hello! I\'m your medical assistant. Please select a department from the right panel to get started.</div>';
            document.getElementById('questionDisplay').innerHTML = '';
            
            // Reset state
            this.currentDepartment = null;
            this.currentQuestion = null;
            this.selectedOptions = [];
            this.answerHistory = [];
            this.currentStep = 0;
            
            // Reset buttons
            document.getElementById('nextButton').disabled = true;
            document.getElementById('nextButton').style.display = 'block';
            document.getElementById('prevButton').style.display = 'none';
            
            // Reset department selection
            document.querySelectorAll('.department-btn').forEach(btn => {
                btn.classList.remove('selected', 'department-highlight');
            });
            
            // Reset header
            document.getElementById('currentDepartment').textContent = 'General Consultation';
            document.getElementById('progressText').textContent = 'Ready';
            
        } catch (error) {
            console.error('Error restarting chat:', error);
        }
    }
}

// Initialize chatbot when page loads
document.addEventListener('DOMContentLoaded', () => {
    new MedicalChatbot();
});