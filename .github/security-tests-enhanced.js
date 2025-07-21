const https = require('https');
const fs = require('fs');

class SecurityTester {
  constructor(baseURL) {
    this.baseURL = baseURL;
    this.results = {
      passed: 0,
      failed: 0,
      warnings: 0,
      tests: []
    };
  }

  async runAllTests() {
    console.log('🔒 Starting Security Tests...\n');
    
    await this.testSecurityHeaders();
    await this.testSSLConfiguration();
    await this.testCookieSecurity();
    await this.testAPIVersioning();
    await this.testErrorHandling();
    await this.testCORS();
    
    this.printSummary();
    return this.results.failed === 0;
  }

  async testSecurityHeaders() {
    console.log('📋 Testing Security Headers...');
    const requiredHeaders = {
      'strict-transport-security': 'HSTS header',
      'x-content-type-options': 'X-Content-Type-Options header', 
      'x-frame-options': 'X-Frame-Options header',
      'x-xss-protection': 'X-XSS-Protection header',
      'content-security-policy': 'Content Security Policy',
      'referrer-policy': 'Referrer Policy'
    };

    try {
      const response = await this.makeRequest('GET', '/');
      const headers = response.headers;

      for (const [header, name] of Object.entries(requiredHeaders)) {
        if (headers[header]) {
          this.addResult('pass', `${name} is set: ${headers[header]}`);
        } else {
          this.addResult('fail', `Missing ${name}`);
        }
      }

      // Check for problematic headers
      if (headers['x-powered-by']) {
        this.addResult('warning', `X-Powered-By header exposed: ${headers['x-powered-by']}`);
      }
      if (headers['server']) {
        this.addResult('warning', `Server header exposed: ${headers['server']}`);
      }
    } catch (error) {
      this.addResult('fail', `Failed to test security headers: ${error.message}`);
    }
  }

  async testSSLConfiguration() {
    console.log('🔐 Testing SSL/TLS Configuration...');
    
    // This is a basic check - for comprehensive SSL testing use testssl.sh
    try {
      const url = new URL(this.baseURL);
      if (url.protocol === 'https:') {
        this.addResult('pass', 'Site is using HTTPS');
        
        // Check for SSL redirect from HTTP
        const httpURL = this.baseURL.replace('https://', 'http://');
        const response = await this.makeRequest('GET', '/', { followRedirect: false, baseURL: httpURL });
        
        if (response.statusCode === 301 || response.statusCode === 302) {
          const location = response.headers.location;
          if (location && location.startsWith('https://')) {
            this.addResult('pass', 'HTTP redirects to HTTPS');
          } else {
            this.addResult('fail', 'HTTP does not redirect to HTTPS properly');
          }
        } else {
          this.addResult('fail', 'HTTP version is accessible without redirect');
        }
      } else {
        this.addResult('fail', 'Site is not using HTTPS');
      }
    } catch (error) {
      this.addResult('warning', `Could not test SSL configuration: ${error.message}`);
    }
  }

  async testCookieSecurity() {
    console.log('🍪 Testing Cookie Security...');
    
    try {
      // Attempt login to get a session cookie
      const loginData = JSON.stringify({
        username: 'security_test_' + Date.now(),
        password: 'test_password_123'
      });

      const response = await this.makeRequest('POST', '/api/auth/login', {
        headers: { 'Content-Type': 'application/json' },
        body: loginData
      });

      const cookies = response.headers['set-cookie'];
      if (cookies) {
        const sessionCookie = Array.isArray(cookies) ? cookies[0] : cookies;
        
        // Check for security flags
        const hasHttpOnly = sessionCookie.toLowerCase().includes('httponly');
        const hasSecure = sessionCookie.toLowerCase().includes('secure');
        const hasSameSite = sessionCookie.toLowerCase().includes('samesite');
        
        if (hasHttpOnly) {
          this.addResult('pass', 'Session cookie has HttpOnly flag');
        } else {
          this.addResult('fail', 'Session cookie missing HttpOnly flag');
        }
        
        if (hasSecure || this.baseURL.startsWith('http://localhost')) {
          this.addResult('pass', 'Session cookie has Secure flag (or is localhost)');
        } else {
          this.addResult('fail', 'Session cookie missing Secure flag');
        }
        
        if (hasSameSite) {
          this.addResult('pass', 'Session cookie has SameSite flag');
        } else {
          this.addResult('fail', 'Session cookie missing SameSite flag');
        }
      }
    } catch (error) {
      this.addResult('warning', `Could not test cookie security: ${error.message}`);
    }
  }

  async testAPIVersioning() {
    console.log('🔄 Testing API Versioning...');
    
    // Check if API supports versioning
    const versioningPatterns = [
      '/api/v1/todos',
      '/api/todos?version=1',
      '/api/todos' // with Accept: application/vnd.api+json;version=1
    ];

    let hasVersioning = false;
    
    for (const pattern of versioningPatterns) {
      try {
        const response = await this.makeRequest('GET', pattern, {
          headers: { 'Accept': 'application/vnd.api+json;version=1' }
        });
        
        if (response.statusCode !== 404) {
          hasVersioning = true;
          this.addResult('pass', `API versioning detected: ${pattern}`);
          break;
        }
      } catch (error) {
        // Continue checking other patterns
      }
    }
    
    if (!hasVersioning) {
      this.addResult('warning', 'API versioning not detected - consider implementing for backward compatibility');
    }
  }

  async testErrorHandling() {
    console.log('⚠️ Testing Error Handling...');
    
    const testCases = [
      { path: '/api/nonexistent', expected: 404, name: 'Non-existent endpoint' },
      { path: '/api/todos/abc', expected: 400, name: 'Invalid ID format' },
      { path: '/api/todos/999999', expected: 404, name: 'Non-existent resource' }
    ];

    for (const test of testCases) {
      try {
        const response = await this.makeRequest('GET', test.path);
        
        if (response.statusCode === test.expected) {
          this.addResult('pass', `${test.name} returns ${test.expected}`);
          
          // Check response doesn't leak sensitive info
          const body = response.body;
          if (body.includes('stack') || body.includes('trace')) {
            this.addResult('fail', `${test.name} exposes stack trace`);
          }
        } else {
          this.addResult('warning', `${test.name} returns ${response.statusCode} instead of ${test.expected}`);
        }
      } catch (error) {
        this.addResult('fail', `Error testing ${test.name}: ${error.message}`);
      }
    }
  }

  async testCORS() {
    console.log('🌐 Testing CORS Configuration...');
    
    const origins = [
      'https://evil.com',
      'http://localhost:3000',
      'null'
    ];

    for (const origin of origins) {
      try {
        const response = await this.makeRequest('OPTIONS', '/api/todos', {
          headers: {
            'Origin': origin,
            'Access-Control-Request-Method': 'POST'
          }
        });

        const allowedOrigin = response.headers['access-control-allow-origin'];
        
        if (allowedOrigin === '*') {
          this.addResult('fail', `CORS allows all origins (*) - this is insecure for authenticated endpoints`);
        } else if (allowedOrigin === origin && origin === 'https://evil.com') {
          this.addResult('fail', `CORS allows untrusted origin: ${origin}`);
        } else if (allowedOrigin === origin && origin === 'null') {
          this.addResult('fail', `CORS allows 'null' origin - this can be exploited`);
        } else if (!allowedOrigin) {
          this.addResult('pass', `CORS properly restricts origin: ${origin}`);
        }
      } catch (error) {
        this.addResult('warning', `Could not test CORS for origin ${origin}: ${error.message}`);
      }
    }
  }

  // Helper methods
  makeRequest(method, path, options = {}) {
    return new Promise((resolve, reject) => {
      const url = new URL((options.baseURL || this.baseURL) + path);
      const reqOptions = {
        method,
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers: options.headers || {},
        rejectUnauthorized: false // Allow self-signed certs for testing
      };

      const req = https.request(reqOptions, (res) => {
        let body = '';
        
        if (!options.followRedirect && (res.statusCode === 301 || res.statusCode === 302)) {
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            body: ''
          });
          return;
        }

        res.on('data', chunk => body += chunk);
        res.on('end', () => {
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            body
          });
        });
      });

      req.on('error', reject);
      
      if (options.body) {
        req.write(options.body);
      }
      
      req.end();
    });
  }

  addResult(type, message) {
    this.results.tests.push({ type, message });
    
    switch (type) {
      case 'pass':
        console.log(`✅ ${message}`);
        this.results.passed++;
        break;
      case 'fail':
        console.log(`❌ ${message}`);
        this.results.failed++;
        break;
      case 'warning':
        console.log(`⚠️  ${message}`);
        this.results.warnings++;
        break;
    }
  }

  printSummary() {
    console.log('\n📊 Test Summary:');
    console.log(`   Passed: ${this.results.passed}`);
    console.log(`   Failed: ${this.results.failed}`);
    console.log(`   Warnings: ${this.results.warnings}`);
    
    if (this.results.failed > 0) {
      console.log('\n❌ Security tests failed! Please address the issues above.');
    } else if (this.results.warnings > 0) {
      console.log('\n⚠️  Security tests passed with warnings. Consider addressing the warnings.');
    } else {
      console.log('\n✅ All security tests passed!');
    }
  }
}

// Run tests if called directly
if (require.main === module) {
  const baseURL = process.argv[2] || 'https://localhost:4321';
  const tester = new SecurityTester(baseURL);
  
  tester.runAllTests().then(success => {
    process.exit(success ? 0 : 1);
  }).catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = SecurityTester;
