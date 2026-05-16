# IP Geolocation Tracker

A web-based educational tool for tracking IP addresses and discovering their geographical locations.

## Features

🌍 **IP Geolocation Lookup**
- Track any public IP address
- Get detailed location information (country, city, coordinates)
- View ISP, timezone, and hostname information

🗺️ **Interactive Map**
- Visualize IP locations on an interactive Leaflet map
- Zoom and pan to explore locations
- Marker-based location display

📊 **Multiple Views**
- **Map View**: Interactive map with location markers
- **Details View**: Comprehensive IP information grid
- **History View**: Track and revisit previous searches

🔍 **Advanced Features**
- **My IP**: Instantly discover your own IP address
- **Batch Lookup**: Look up multiple IPs at once (up to 10)
- **Search History**: Automatic tracking of searches with localStorage
- **Reverse DNS**: Hostname lookup for IP addresses

## Installation

### Requirements
- Python 3.7+
- Flask 2.3+
- Requests library

### Setup

1. Clone the repository:
```bash
git clone https://github.com/k14321035-cmd/network.git
cd network
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python ip_geolocation_tracker.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## Docker Support

Build and run with Docker:

```bash
docker build -t ip-geolocation-tracker .
docker run -p 5000:5000 ip-geolocation-tracker
```

## API Endpoints

### Single IP Lookup
```
POST /api/lookup
Content-Type: application/json

{
  "ip": "8.8.8.8"
}
```

### Get Your IP
```
GET /api/my-ip
```

### Batch Lookup
```
POST /api/batch-lookup
Content-Type: application/json

{
  "ips": ["8.8.8.8", "1.1.1.1", "208.67.222.123"]
}
```

### Validate IP
```
POST /api/validate-ip
Content-Type: application/json

{
  "ip": "8.8.8.8"
}
```

## Response Format

```json
{
  "ip": "8.8.8.8",
  "country": "United States",
  "country_code": "US",
  "region": "California",
  "city": "Mountain View",
  "latitude": 37.4419,
  "longitude": -122.1430,
  "timezone": "America/Los_Angeles",
  "isp": "Google LLC",
  "hostname": "dns.google",
  "type": "ipv4",
  "source": "ipwho",
  "timestamp": "2026-05-16T12:00:00"
}
```

## Technologies Used

**Backend:**
- Flask (Python web framework)
- Requests (HTTP library)
- IP Geolocation APIs (ipwho.is, ip-api.com)

**Frontend:**
- HTML5
- CSS3
- Vanilla JavaScript
- Leaflet.js (Interactive maps)
- LocalStorage (Search history)

## Data Sources

This tool uses multiple geolocation data sources:
1. **ipwho.is** - Primary IP geolocation API
2. **ip-api.com** - Fallback geolocation API

## Educational Purpose

This is an **educational tool** designed to teach:
- Network fundamentals
- IP address concepts
- Geolocation technologies
- REST API consumption
- Web development

**Note:** Use responsibly and only for authorized lookups and learning purposes.

## Legal Disclaimer

🛡️ **Important:**
- This tool should only be used for legitimate educational and security purposes
- Always obtain authorization before performing IP lookups
- Do not use for unauthorized surveillance, hacking, or illegal activities
- Comply with all local laws and regulations

## Features Coming Soon

- 🌐 VPN/Proxy detection
- 🛡️ Threat detection
- 🗂️ Bulk IP analysis
- 📈 Advanced statistics
- 🔐 Private/Internal IP handling

## License

MIT License - See LICENSE file for details

## Support

For issues and feature requests, please open an issue on GitHub.

---

**Created:** May 2026  
**Last Updated:** May 16, 2026  
**Author:** k14321035-cmd
