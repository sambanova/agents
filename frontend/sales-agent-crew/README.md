![Samba Sales Co-Pilot Logo](https://sambanova.ai/hubfs/sambanova-logo-black.png)

# SambaNova Agents

An intelligent sales and research assistant powered by SambaNova AI. This application helps sales teams and researchers by automatically:

- Generating qualified sales information with company insights
- Creating detailed research reports and educational content
- Intelligently routing queries to the appropriate service
- Supporting voice input for natural interaction

## Features

### General Assistant
The application includes a general-purpose AI assistant that can help with:
- Answering basic questions and queries
- Providing explanations and clarifications
- Offering technical support
- Assisting with general research tasks

Example General Queries:
- "What's the difference between supervised and unsupervised learning?"
- "Can you explain how REST APIs work?"
- "What are the best practices for data visualization?"
- "How do I optimize database queries?"
- "Explain the concept of containerization"

### Intelligent Query Routing

The application automatically determines whether your query is best suited for:

- Sales lead Information Gathering
- Educational content/research creation
- Financial Analysis and Market Research
- More tasks to come!

### Sales Lead Information

When in sales mode, Samba Co-Pilot will:

- Find relevant companies matching your criteria
- Extract key company information
- Provide funding status and insights
- Generate customized sales approaches

Example Sales Queries:
- "Find AI startups in Silicon Valley with Series B funding"
- "Which healthcare companies in Boston are working on drug discovery?"
- "Show me cybersecurity companies in Israel with enterprise clients"
- "Find sustainable energy startups in Nordic countries"
- "Show me B2B SaaS companies in Singapore with over 100 employees"

### Research & Content Generation

For research queries, the system will:

- Analyze topics in-depth
- Create structured research reports
- Provide educational content
- Include relevant citations and sources

Example Research Queries:
- "Explain quantum computing and its applications in cryptography"
- "How does CRISPR gene editing work in modern medicine?"
- "What's the relationship between AI and neuromorphic computing?"
- "Explain the impact of blockchain on supply chain management"
- "How do machine learning algorithms handle natural language processing?"
- "What are the latest developments in fusion energy research?"

### Financial Analysis & Market Research
For financial queries, Samba Co-Pilot will:
- Analyze company financial performance
- Track market trends and competitive positioning
- Evaluate stock performance and valuation metrics
- Generate investment insights
- Monitor industry-specific metrics
- Compare companies within sectors

Example Financial Queries:
- "Analyze Tesla's recent performance and future growth prospects"
- "How is the semiconductor industry performing this quarter?"
- "Compare cloud revenue growth between Microsoft Azure and AWS"
- "What's the market outlook for AI chip manufacturers?"
- "Evaluate Apple's financial health considering recent product launches"
- "Compare profitability metrics between major EV manufacturers"

### Voice Input Support

- Click the microphone icon to start voice input
- Automatic transcription of speech to text
- Hands-free operation support

### Additional Features

- 🔐 Secure API key management with encryption
- 📜 Chat history tracking
- 📥 Results export functionality
- 🔄 Real-time query routing
- 📊 Detailed company insights
- 💹 Financial analysis and market trends
- ✍️ AI-generated outreach templates

## Technical Setup

### Prerequisites

- Python 3.8 or higher.
- Node.js 16 or higher.
- Yarn.
- API Keys:
  - SambaNova API key. get it from https://cloud.sambanova.ai/
  - Serper API key (for web search). get it from https://serper.dev/
  - Exa API key (for company data). get it from https://exa.co/

> **Important**: Click the settings gear icon ⚙️ to configure your API keys. The application requires these keys to function properly.

### Authentication

The application supports authentication using access tokens. You can provide an access token in several ways:

1. **URL Parameter**: Open the app with a token in the URL: `http://localhost:5174/?token=your_access_token`

2. **Token Dialog**: Click the key icon in the header to manually set or update your access token.

3. **Programmatically**: Access the root Vue instance to set the token: `app.$root.setAuthToken('your_token')`

The token will be stored securely in localStorage and automatically included in all API requests.

### Frontend

For the following commands, go to `/frontend/sales-agent-crew/` directory.

#### Install Vue.js dependencies

```bash
yarn install
```

#### Run a local development environment

```bash
yarn dev
```

#### Create a production build

```bash
yarn build
```

### Backend

For the following commands, go to `/backend/` directory.

#### Install Python dependencies

Create and activate a virtual environment (for example with venv) and install the project dependencies inside it.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Run the application

```bash
uvicorn api.main:app --reload
```

## Environment Variables

For the frontend, go to `/frontend/sales-agent-crew/` and create a `.env` file with:

```bash
VITE_API_URL=your_api_url
```

## Running the Application

1. Start the FastAPI backend server:

```bash
# From the project root
cd backend
uvicorn api.main:app --reload
```

2. Start the Vue.js frontend development server:

```bash
# From the project root
cd frontend/sales-agent-crew/
yarn dev
```

3. Open your browser and navigate to:\*

```bash
 http://localhost:5174/
```

\*Update the URL in the LeadGenerationAPI CORS API if it's different.

## API Keys Setup

Access the settings modal to configure your:

- SambaNova API key
- Serper API key
- Exa API key

All keys are encrypted before storaging them in localStorage.

## Architecture

![Co-Pilot Architecture Diagram](backend/Co-Pilot%20Workflow-2025-02-21-221704.png)

Built with:

- Vue 3 + Composition API
- Vite
- TailwindCSS
- Token-based authentication
- Axios for API calls

## Tech Stack

### Frontend

- Vue.js 3 (Composition API)
- TailwindCSS for styling
- Vite for build tooling
- Token-based authentication

### Backend Integration

- FastAPI
- CrewAI
- SambaNova Agentic Cloud
- Exa Search API
- Financial Data APIs

## Usage

1. **Configure API Keys**

   - Open settings
   - Enter your API keys
   - Keys are securely encrypted

2. **Start Searching**

   - Type your query or use voice input
   - System automatically determines query type
   - Receive structured results

3. **View Results**
   - Sales information displayed as cards
   - Research shown as structured reports
   - Export functionality available
   - Save important searches

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

[MIT License](LICENSE)
