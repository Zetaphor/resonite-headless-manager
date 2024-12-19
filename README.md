# Resonite Headless Manager

A web-based management interface for Resonite headless servers running in Docker containers. This application provides real-time monitoring and control of your Resonite worlds through an intuitive web interface.

![image](https://github.com/user-attachments/assets/ba5a5e28-639d-47bd-b133-5ba4727a91a2)



## Features

- Real-time Monitoring
  - Live container status and system resource usage
  - Active worlds overview with detailed statistics
  - Connected users monitoring with presence status
  - System CPU and memory usage tracking

- World Management
  - View and modify world properties
  - Control world visibility and access levels
  - Manage maximum user limits
  - Save, restart, or close worlds

- User Management
  - Real-time user monitoring
  - User role management
  - Kick, ban, and silence controls
  - Friend request handling
  - Ban list management

- **Server Configuration**
  - Built-in configuration editor
  - JSON validation and formatting
  - Live configuration updates

- **Console Access**
  - Direct access to server console
  - Real-time command output

## Prerequisites

- Python 3.7+
- Docker
- Resonite Headless Server running in a Docker container. I personally use [this setup from ShadowPanther](https://github.com/shadowpanther/resonite-headless).

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/resonite-headless-manager.git
cd resonite-headless-manager
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables:

```bash
export CONTAINER_NAME=your-container-name
export CONFIG_PATH=/path/to/your/headless/Config.json
```

4. Run the server:

```bash
python server.py
```

## Security Considerations

This application is designed for local network use. If exposing to the internet:

- Use a reverse proxy with SSL/TLS
- Implement proper authentication
- Configure appropriate firewall rules

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an issue.

## Written in collaboration with Claude 3.5 Sonnet

This code was written with the help of Claude 3.5 Sonnet by Anthropic.

## License

This project is open-sourced under the MIT License - see the LICENSE file for details.
