![Samba Agents Logo](https://sambanova.ai/hubfs/sambanova-logo-black.png)

<h1 style="font-size: 3em;">Agents</h1>

This kit is an example of how a local application can be created, configured and launched to leverage SambaNova's Agents Cloud.  The Agents application routes requests to four different agents: General assistant agent, Sales leads agent, Deep research agent, and a Finance analysis agent. The agents process tens of thousands of tokens that generates lightning fast and accurate results. The Agents application helps sales teams and researchers by:

- Generating qualified sales information with company insights.
- Creating detailed research reports and educational content.
- Intelligently routing queries to the appropriate service.
- Supporting voice input for natural interaction.

The basic process of the Agents application is described below.

1. User query processing
   - User submits a query via text or voice input.
   - The application analyzes the query to determine its category (general assistance, sales leads, research, or financial analysis).

1. Agent assignment
   - The query is routed to the appropriate agent based on content and intent.
   - If the query spans multiple domains, agents collaborate to provide a comprehensive response.
   
1. Data retrieval and processing
   - The selected agent fetches relevant data from available APIs and knowledge bases.
   - AI models process and structure the information for clarity and accuracy.
   
1. Response generation
   - The application generates a structured response.
   - The response is formatted based on the query type (e.g., report format for research, tabular format for financial analysis).

1. User interaction and feedback
   - The user reviews the response and may refine the query.
   - The system continuously learns from interactions to improve future responses.

> **Note**: View the **Agent Reasoning** panel on the right side of the application to see the real-time thought output.

# Prerequisites

## Required software packages
   - [Python 3.11](https://www.python.org/downloads/release/python-31111/) (exact version required)
   - [Node.js 18.17.0 or later](https://nodejs.org/en/download)
   - [Yarn](https://classic.yarnpkg.com/en/docs/install)
   - [Redis](https://redis.io/download) (via Docker or Homebrew)
     
      ```bash
      # Install Redis with Docker
      docker run --name redis -p 6379:6379 -d redis
      ```
      ```bash
      # Install Redis with Homebrew on macOS
      brew install redis
      brew services start redis
      ```

## Required APIs
You will need to create free accounts to access these APIs:
   - [SambaNova API key](https://cloud.sambanova.ai/) for agent models
   - [Serper API key](https://serper.dev/) for web search
   - [Exa API key](https://exa.co/) for company data
   - [Tavily API key](https://tavily.com/) for deep research capabilities

>**Note**: The DeepSeek-R1-8K model is supported in the application provided you have access to it.

## Clerk authentication setup

1. Sign up for a free Clerk account at [clerk.com](https://clerk.com/).
1. Create a new application in the Clerk dashboard.
1. Get your publishable key and secret key.
1. Configure your JWT issuer URL.
1. Add these values to your environment variables as shown above.

# Using the Application

You can setup and run the application in two ways: the cloud-hosted version or the locally-hosted version.

## Cloud Hosted

This version is hosted on SambaNova Cloud. No need to install dependencies locally.  Just set up an account and use your SambaNova Cloud API Key.

1. Go to the [Agents application](https://aiskagents.cloud.snova.ai/) login page.
1. Sign in using Clerk authentication (you will receive an email with login instructions).
1. Once you login, go to settings and add the SambaNova Cloud API key.
1. Start using the application to enhance sales workflows, conduct research, and gain actionable insights.

## Locally Hosted

### Frontend setup

Follow the steps below to install the frontend for the Agents application.

> **Note**: For the following commands, go to `/frontend/sales-agent-crew/` directory.

1. Install Vue.js dependencies.

   ```bash
   yarn install
   ```

1. When you have completed the backend setup, you can either:
   + Run a local development environment.

   ```bash
   yarn dev
   ```

   + Or, create a production build.

   ```bash
   yarn build
   ```

### Backend setup

Follow the steps below to install the backend for the Agents application.

> **Note**: For the following commands, go to `/backend/` directory.

1. Install Python dependencies: Create and activate a virtual environment (for example with venv) and install the project dependencies inside it. Make sure to use Python 3.11.

   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Environment variables setup

#### Frontend environment variables

> **Note**: For the frontend environment variables, go to `/frontend/sales-agent-crew/`.

1. Create a `.env` file with the following variables.
   ```bash
   # Clerk Keys
   CLERK_SECRET_KEY="<your_clerk_secret_key>"
   VITE_CLERK_PUBLISHABLE_KEY="<your_clerk_publishable_key>"

   # Vite Settings
   VITE_API_URL=/api
   VITE_WEBSOCKET_URL=ws://localhost:8000
   VITE_ENABLE_WORKFLOW_TOGGLE=false
   VITE_ENABLE_USER_KEYS=false
   ```

#### Backend environment variables

> **Note**: For the backend environment variables, go to `/backend/`.

1. Create a `.env` file with the following required variables.
   ```bash
   # Authentication
   CLERK_JWT_ISSUER="https://your-clerk-instance.clerk.accounts.dev/.well-known/jwks.json"
   
   # API Keys for Services
   EXA_API_KEY="<your_exa_api_key>"
   SERPER_API_KEY="<your_serper_api_key>"
   TAVILY_API_KEY="<your_tavily_api_key>"  # Required for Deep Research agent

   # Additional Settings
   ENABLE_TRACING="false"
   OTEL_SDK_DISABLED="true"
   LOG_DIR="/app/logs"
   ENABLE_USER_KEYS="false"

   # Optional: For usage tracking
   LANGTRACE_API_KEY=your_langtrace_api_key

   #Redis Master Salt Key - User should set to any value they wish
   REDIS_MASTER_SALT=abc123def456
   ```


### Starting the Application

1. Start the FastAPI backend server:

   ```bash
   # From the project root
   cd backend
   uvicorn api.lead_generation_api:create_app --reload --host 127.0.0.1 --port 8000
   ```

1. Start the `Vue.js` frontend development server:

   ```bash
   # From the project root
   cd frontend/sales-agent-crew/

   # For a development deployment
   yarn dev

   # For a production deployment
   yarn build
   ```

1. When you launch the front end, Vite will give you the localhost URL.  Open your browser and navigate to:

   ```bash
   http://localhost:<port_from_vite>/
   ```


### API keys setup

You can access the settings modal to configure the API keys mentioned in the [prerequisites](#prerequisites) section.

### (Optional) LangTrace integration

If you want to track usage and monitor the application's performance:

1. Sign up for a LangTrace account
1. Add your LangTrace API key to the backend `.env` file
1. The application will automatically log traces (disabled by default)

# Architecture

![Agents Architecture Diagram](backend/images/architecture-diagram.jpg)

This application is built with:

- Vue 3 + Composition API
- Vite
- TailwindCSS
- Clerk for authentication
- Axios for API calls

# Technology stack

The stack is designed to offer high-performance and scalability for both frontend and backend needs. See the frontend and backend technology stack listed in the table below.

<table style="width:40%; border: 1px solid #000; border-collapse: collapse;">
  <thead>
      <tr style="background-color: #f0f0f0;"> <!-- Shading applied here -->
      <th style="border: 1px solid #000; width: 30%; text-align: left; vertical-align: top;">Category</th>
      <th style="border: 1px solid #000; width: 80%; text-align: left; vertical-align: top;">Technologies used</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="border: 1px solid #000; width: 30%; text-align: left; vertical-align: top;"><strong>Frontend</strong></td>
      <td style="border: 1px solid #000; width: 80%; text-align: left; vertical-align: top;">
        <ul>
          <li>Vue.js 3 (Composition API)</li>
          <li>TailwindCSS for styling</li>
          <li>Vite for build tooling</li>
          <li>Clerk for authentication</li>
        </ul>
      </td>
    </tr>
    <tr>
      <td style="border: 1px solid #000; width: 30%; text-align: left; vertical-align: top;"><strong>Backend</strong></td>
      <td style="border: 1px solid #000; width: 80%; text-align: left; vertical-align: top;">
        <ul>
          <li>FastAPI</li>
          <li>CrewAI</li>
          <li>SambaNova Agentic Cloud</li>
          <li>Exa Search API</li>
          <li>Tavily API for research</li>
          <li>Redis for caching</li>
          <li>Financial Data APIs</li>
        </ul>
      </td>
    </tr>
  </tbody>
</table>


# Features

This section describes the agents and feature capabilities of the application. 

## General assistant

The General assistant agent helps with:

- Answering basic questions and queries.
- Providing explanations and clarifications.
- Offering technical support.
- Assisting with general research tasks.

### Example queries

Example queries for general assistance are listed below.

- "What's the difference between supervised and unsupervised learning?"
- "Can you explain how REST APIs work?"
- "What are the best practices for data visualization?"
- "How do I optimize database queries?"
- "Explain the concept of containerization"

## Sales leads

The application uses the Sales leads agent to:

- Find relevant companies matching your criteria.
- Extract key company information.
- Provide funding status and insights.
- Generate customized sales approaches.

### Example queries

Example queries for sales leads information are listed below.

- "Find AI startups in Silicon Valley with Series B funding"
- "Which healthcare companies in Boston are working on drug discovery?"
- "Show me cybersecurity companies in Israel with enterprise clients"
- "Find sustainable energy startups in Nordic countries"
- "Show me B2B SaaS companies in Singapore with over 100 employees"

## Deep research

For research queries, the application uses the Deep research agent to:

- Analyze topics in-depth.
- Create structured research reports.
- Provide educational content.
- Include relevant citations and sources.

### Example queries

Example queries for research and content generation are listed below.

- "Explain quantum computing and its applications in cryptography"
- "How does CRISPR gene editing work in modern medicine?"
- "What's the relationship between AI and neuromorphic computing?"
- "Explain the impact of blockchain on supply chain management"
- "How do machine learning algorithms handle natural language processing?"
- "What are the latest developments in fusion energy research?"

## Financial analysis

For financial queries, the application uses the Financial analysis agent to:

- Analyze company financial performance.
- Track market trends and competitive positioning.
- Evaluate stock performance and valuation metrics.
- Generate investment insights.
- Monitor industry-specific metrics.
- Compare companies within sectors.

### Example queries

Example queries for financial analysis and market research are listed below.

- "Analyze Tesla's recent performance and future growth prospects"
- "How is the semiconductor industry performing this quarter?"
- "Compare cloud revenue growth between Microsoft Azure and AWS"
- "What's the market outlook for AI chip manufacturers?"
- "Evaluate Apple's financial health considering recent product launches"
- "Compare profitability metrics between major EV manufacturers"

## Intelligent query routing

The application automatically determines the best category for your query, ensuring efficient processing. Query routing is automatically done for use-cases such as:

- Sales lead information gathering
- Educational content/research creation
- Financial analysis and market research

## Voice input support

The application allows you to make queries using audio input. Simply click the microphone icon to start speaking. It also offers:

- Automatic speech-to-text transcription
- Hands-free operation for convenience

## Additional features

Additional features of the application are listed below.

- 🔐 Secure API key management – Encrypted for maximum protection
- 📜 Chat history tracking – Easily access past conversations
- 📥 Results export functionality – Download and share insights effortlessly
- 🔄 Real-time query routing – Instant categorization for accurate responses
- 📊 Detailed company insights – In-depth business data at your fingertips
- 💹 Financial analysis and market trends – Stay ahead with real-time analytics
- ✍ AI-generated outreach templates – Craft professional messages instantly


# Usage

1. **Configure API keys**

   - Open settings
   - Enter your API keys
   - Keys are securely encrypted

1. **Start searching**

   - Type your query or use voice input
   - System automatically determines query type
   - Receive structured results

1. **View results**
   - Sales information displayed as cards
   - Research shown as structured reports
   - Export functionality available
   - Save important searches

# Contributing

1. Fork the repository
1. Create your feature branch
1. Commit your changes
1. Push to the branch
1. Create a new pull request

# License

[MIT License](LICENSE)
