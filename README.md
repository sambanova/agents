![Samba Agents Logo](https://sambanova.ai/hubfs/sambanova-logo-black.png)

<h1 style="font-size: 3em;">Agents</h1>

The Agents application routes requests to four different agents: General assistant agent, Sales leads agent, Deep research agent, and a Finance analysis agent. The agents process tens of thousands of tokens that generates lightning fast and accurate results. The Agents application helps sales teams and researchers by:

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

# Prerequisites

Ensure to install the prerequisites.
   - [Python 3.8 or later](https://www.python.org/downloads/)
   - [Node.js 16 or later](https://nodejs.org/en/download)
   - [Yarn](https://classic.yarnpkg.com/en/docs/install)

Get the following API keys to setup the Agents application.
   - [SambaNova API key](https://cloud.sambanova.ai/)
   - [Serper API key](https://serper.dev/) for web search
   - [Exa API key](https://exa.co/) for company data
   - [Fireworks API key](https://fireworks.ai/) 

# Setup and run the application

You can setup and run the application in two ways - Cloud hosted version or locally hosted version.

## Cloud hosted version

This version is hosted on SambaNova Cloud. No need to install dependencies locally.

1. Go to the [Agents application](https://aiskagents.cloud.snova.ai/) login page.
1. Sign in using Clerk authentication (you will receive an email with login instructions).
1. Once you login, go to settings and add the API keys.
1. Start using the application to enhance sales workflows, conduct research, and gain actionable insights.

## Locally hosted version

### Frontend setup

Follow the steps below to install the frontend for the Agents application.

> **Note**: For the following commands, go to `/frontend/sales-agent-crew/` directory.

1. Install Vue.js dependencies

   ```bash
   yarn install
   ```

1. Run a local development environment

   ```bash
   yarn dev
   ```

1. Create a production build

   ```bash
   yarn build
   ```

### Backend setup

Follow the steps below to install the backend for the Agents application.

> **Note**: For the following commands, go to `/backend/` directory.

1. Install Python dependencies - Create and activate a virtual environment (for example with venv) and install the project dependencies inside it.

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the application

   ```bash
   uvicorn api.main:app --reload
   ```

### Environment variables setup

> **Note**: For the frontend environment variables, go to `/frontend/sales-agent-crew/`.

1. Create a `.env` file.
   ```bash
   VITE_API_URL=your_api_url
   ```

1. Start the FastAPI backend server.

   ```bash
   # From the project root
   cd backend
   uvicorn api.main:app --reload
   ```

2. Start the Vue.js frontend development server.

   ```bash
   # From the project root
   cd frontend/sales-agent-crew/
   yarn dev
   ```

3. Open your browser and navigate to:

   ```bash
   http://localhost:5174/
   ```

### API keys setup

1. Access the settings modal to configure the API keys mentioned in the [prerequisites](#prerequisites) section.
1. Ensure that API keys are encrypted before storing them in localStorage.

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

- Analyze topics in-depth
- Create structured research reports
- Provide educational content
- Include relevant citations and sources

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

- Analyze company financial performance
- Track market trends and competitive positioning
- Evaluate stock performance and valuation metrics
- Generate investment insights
- Monitor industry-specific metrics
- Compare companies within sectors

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

# Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

# License

[MIT License](LICENSE)
