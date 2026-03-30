# Nexus Web Dashboard

A CI/CD-style visualization dashboard for monitoring agent workflows and execution pipelines.

## Features

- **Agent Workflow Visualization**: View agent execution status in a CI/CD pipeline style
- **Five Stage Pipeline**: Init → GitHub Operations → Work → Git Operations → Finish
- **Real-time Status Indicators**: Visual indicators for running, completed, failed, and error states
- **Stage Details**: Click on any stage to view detailed logs and execution information
- **Workflow Statistics**: Overview of running, completed, and failed workflows
- **Responsive Design**: Works on desktop and mobile devices

## Tech Stack

- **React 19** - Modern React with TypeScript
- **Vite** - Fast development and build tool
- **Tailwind CSS v4** - Utility-first CSS framework
- **shadcn/ui** - Reusable UI components
- **Radix UI** - Unstyled, accessible UI primitives
- **Lucide React** - Beautiful icons

## Getting Started

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Build

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── components/
│   └── ui/           # shadcn/ui components
├── data/
│   └── mockWorkflows.ts  # Mock data for testing
├── lib/
│   └── utils.ts      # Utility functions
├── pages/
│   └── LogPage.tsx   # Main dashboard page
├── types/
│   └── agent.ts      # TypeScript type definitions
├── App.tsx           # Root component
└── index.css         # Global styles
```

## Agent Workflow Stages

Each agent workflow consists of five stages:

1. **Init** - Initialize environment and configuration
2. **GitHub Operations** - Fetch repository data, create issues, manage PRs
3. **Work** - Execute main agent tasks and processing
4. **Git Operations** - Commit changes, push to remote
5. **Finish** - Complete workflow and cleanup

## Stage Status Types

- **Pending** (Gray) - Stage waiting to start
- **Running** (Blue) - Stage currently executing with animated indicator
- **Completed** (Green) - Stage finished successfully
- **Failed** (Red) - Stage failed with error
- **Error** (Amber) - Stage encountered an error condition

## License

MIT
