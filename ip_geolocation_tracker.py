"""
IP Geolocation Tracker
A web-based tool for tracking IP addresses and displaying geographical information
"""

from flask import Flask, render_template, request, jsonify
import requests
import socket
import json
import logging
from functools import lru_cache
from datetime import datetime
import os

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# IP Geolocation API endpoints
IPIFY_API = "https://ipwho.is"
MAXMIND_API = "https://geoip.maxmind.com"
IPSTACK_FALLBACK = "https://ip-api.com/json"


class IPGeolocationTracker:
    """Main IP Geolocation Tracker Class"""
    
    @staticmethod
    def get_client_ip(request_obj):
        """Get client's real IP address"""
        if request_obj.headers.get('X-Forwarded-For'):
            return request_obj.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request_obj.remote_addr
    
    @staticmethod
    @lru_cache(maxsize=128)
    def is_valid_ip(ip_address):
        """Validate IP address format"""
        try:
            socket.inet_aton(ip_address)
            return True
        except socket.error:
            return False
    
    @staticmethod
    def fetch_ipwho_data(ip_address):
        """Fetch data from ipwho.is API"""
        try:
            response = requests.get(f"{IPIFY_API}/{ip_address}", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data.get('success'):
                return {
                    'ip': ip_address,
                    'country': data.get('country'),
                    'country_code': data.get('country_code'),
                    'region': data.get('region'),
                    'city': data.get('city'),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'timezone': data.get('timezone', {}).get('id'),
                    'isp': data.get('connection', {}).get('isp'),
                    'type': data.get('type'),
                    'source': 'ipwho'
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching from ipwho: {str(e)}")
            return None
    
    @staticmethod
    def fetch_ipapi_data(ip_address):
        """Fetch data from ip-api.com as fallback"""
        try:
            response = requests.get(f"{IPSTACK_FALLBACK}/{ip_address}", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'ip': ip_address,
                    'country': data.get('country'),
                    'country_code': data.get('countryCode'),
                    'region': data.get('regionName'),
                    'city': data.get('city'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'timezone': data.get('timezone'),
                    'isp': data.get('isp'),
                    'org': data.get('org'),
                    'type': data.get('type'),
                    'source': 'ip-api'
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching from ip-api: {str(e)}")
            return None
    
    @staticmethod
    def get_geolocation(ip_address):
        """Get geolocation data from multiple sources"""
        if not IPGeolocationTracker.is_valid_ip(ip_address):
            return {'error': 'Invalid IP address format'}
        
        # Try primary API first
        data = IPGeolocationTracker.fetch_ipwho_data(ip_address)
        
        # Fallback to secondary API if primary fails
        if not data:
            data = IPGeolocationTracker.fetch_ipapi_data(ip_address)
        
        if not data:
            return {'error': 'Could not retrieve geolocation data'}
        
        return data
    
    @staticmethod
    def reverse_dns_lookup(ip_address):
        """Perform reverse DNS lookup"""
        try:
            hostname = socket.gethostbyaddr(ip_address)[0]
            return hostname
        except (socket.herror, socket.error):
            return "Not Available"
    
    @staticmethod
    def get_rdns_ptr(ip_address):
        """Get PTR record information"""
        try:
            return IPGeolocationTracker.reverse_dns_lookup(ip_address)
        except:
            return "Not Available"


# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/lookup', methods=['POST'])
def lookup_ip():
    """API endpoint for IP lookup"""
    try:
        data = request.get_json()
        ip_address = data.get('ip', '').strip()
        
        if not ip_address:
            # If no IP provided, get client's IP
            ip_address = IPGeolocationTracker.get_client_ip(request)
        
        if not IPGeolocationTracker.is_valid_ip(ip_address):
            return jsonify({'error': 'Invalid IP address'}), 400
        
        # Get geolocation data
        geo_data = IPGeolocationTracker.get_geolocation(ip_address)
        
        if 'error' in geo_data:
            return jsonify(geo_data), 404
        
        # Add reverse DNS lookup
        geo_data['hostname'] = IPGeolocationTracker.get_rdns_ptr(ip_address)
        geo_data['timestamp'] = datetime.now().isoformat()
        
        return jsonify(geo_data), 200
    
    except Exception as e:
        logger.error(f"Error in lookup_ip: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/my-ip', methods=['GET'])
def get_my_ip():
    """Get client's own IP address"""
    try:
        client_ip = IPGeolocationTracker.get_client_ip(request)
        geo_data = IPGeolocationTracker.get_geolocation(client_ip)
        
        if 'error' in geo_data:
            return jsonify({'ip': client_ip, 'error': 'Could not fetch location'}), 200
        
        geo_data['hostname'] = IPGeolocationTracker.get_rdns_ptr(client_ip)
        geo_data['timestamp'] = datetime.now().isoformat()
        
        return jsonify(geo_data), 200
    
    except Exception as e:
        logger.error(f"Error in get_my_ip: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/batch-lookup', methods=['POST'])
def batch_lookup():
    """Batch lookup multiple IPs"""
    try:
        data = request.get_json()
        ips = data.get('ips', [])
        
        if not isinstance(ips, list) or len(ips) == 0:
            return jsonify({'error': 'Invalid IPs array'}), 400
        
        if len(ips) > 10:
            return jsonify({'error': 'Maximum 10 IPs per batch'}), 400
        
        results = []
        for ip in ips:
            ip = ip.strip()
            if IPGeolocationTracker.is_valid_ip(ip):
                geo_data = IPGeolocationTracker.get_geolocation(ip)
                if 'error' not in geo_data:
                    results.append(geo_data)
        
        return jsonify({'results': results, 'count': len(results)}), 200
    
    except Exception as e:
        logger.error(f"Error in batch_lookup: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/validate-ip', methods=['POST'])
def validate_ip():
    """Validate IP address format"""
    try:
        data = request.get_json()
        ip = data.get('ip', '').strip()
        
        is_valid = IPGeolocationTracker.is_valid_ip(ip)
        return jsonify({'ip': ip, 'valid': is_valid}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
