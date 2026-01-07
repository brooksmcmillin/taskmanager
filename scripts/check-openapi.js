#!/usr/bin/env node
/* eslint-disable security/detect-non-literal-fs-filename, security/detect-non-literal-regexp */
/**
 * OpenAPI Route Coverage Check
 *
 * Validates that all API endpoints in src/pages/api are documented in openapi.yaml
 * and vice versa. Exits with code 1 if there are discrepancies.
 *
 * Note: This script intentionally uses dynamic paths and regex for file traversal.
 */

import { readFileSync, readdirSync, statSync } from 'fs';
import { join, relative } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'];

/**
 * Recursively find all .js files in a directory
 */
function findJsFiles(dir, files = []) {
  const entries = readdirSync(dir);
  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      findJsFiles(fullPath, files);
    } else if (entry.endsWith('.js')) {
      files.push(fullPath);
    }
  }
  return files;
}

/**
 * Extract exported HTTP methods from a JS file
 */
function extractHttpMethods(filePath) {
  const content = readFileSync(filePath, 'utf-8');
  const methods = [];

  for (const method of HTTP_METHODS) {
    // Match patterns like: export const GET = or export async function GET
    const patterns = [
      new RegExp(`export\\s+const\\s+${method}\\s*=`, 'm'),
      new RegExp(`export\\s+async\\s+function\\s+${method}\\s*\\(`, 'm'),
      new RegExp(`export\\s+function\\s+${method}\\s*\\(`, 'm'),
    ];

    if (patterns.some((pattern) => pattern.test(content))) {
      methods.push(method.toLowerCase());
    }
  }

  return methods;
}

/**
 * Convert file path to OpenAPI route path
 * e.g., src/pages/api/todos/[id].js -> /todos/{id}
 */
function filePathToRoute(filePath, apiDir) {
  let route = relative(apiDir, filePath);

  // Remove .js extension
  route = route.replace(/\.js$/, '');

  // Convert [param] to {param}
  route = route.replace(/\[([^\]]+)\]/g, '{$1}');

  // Handle index files
  route = route.replace(/\/index$/, '');

  // Ensure leading slash
  route = '/' + route;

  // Normalize path separators for Windows
  route = route.replace(/\\/g, '/');

  return route;
}

/**
 * Parse openapi.yaml and extract paths with their methods
 */
function parseOpenApiPaths(openapiPath) {
  const content = readFileSync(openapiPath, 'utf-8');
  const paths = new Map();

  // Simple YAML parsing for paths section
  const lines = content.split('\n');
  let currentPath = null;
  let inPathsSection = false;
  let pathIndent = 0;

  for (const line of lines) {
    // Detect paths: section
    if (/^paths:\s*$/.test(line)) {
      inPathsSection = true;
      continue;
    }

    if (!inPathsSection) continue;

    // Detect new top-level section (end of paths)
    if (/^[a-z]+:\s*$/i.test(line) && !line.startsWith(' ')) {
      break;
    }

    // Match path definition (e.g., "  /todos:")
    const pathMatch = line.match(/^(\s{2})(\/.+?):\s*$/);
    if (pathMatch) {
      currentPath = pathMatch[2];
      pathIndent = 2;
      paths.set(currentPath, []);
      continue;
    }

    // Match HTTP method under current path
    if (currentPath) {
      const methodMatch = line.match(
        /^(\s{4})(get|post|put|delete|patch|options):\s*$/
      );
      if (methodMatch) {
        paths.get(currentPath).push(methodMatch[2]);
      }
    }
  }

  return paths;
}

/**
 * Main validation function
 */
function validate() {
  const apiDir = join(projectRoot, 'src', 'pages', 'api');
  const openapiPath = join(projectRoot, 'openapi.yaml');

  console.log('🔍 Checking OpenAPI spec against API endpoints...\n');

  // Get all API endpoints from code
  const codeEndpoints = new Map();
  const jsFiles = findJsFiles(apiDir);

  for (const file of jsFiles) {
    const route = filePathToRoute(file, apiDir);
    const methods = extractHttpMethods(file);
    if (methods.length > 0) {
      codeEndpoints.set(route, methods);
    }
  }

  // Get all paths from OpenAPI spec
  const specPaths = parseOpenApiPaths(openapiPath);

  // Compare and collect discrepancies
  const missingInSpec = [];
  const missingInCode = [];
  const methodMismatches = [];

  // Check code endpoints against spec
  for (const [route, methods] of codeEndpoints) {
    if (!specPaths.has(route)) {
      missingInSpec.push({ route, methods });
    } else {
      const specMethods = specPaths.get(route);
      const missingMethods = methods.filter(
        (m) => !specMethods.includes(m) && m !== 'options'
      );
      const extraMethods = specMethods.filter(
        (m) => !methods.includes(m) && m !== 'options'
      );

      if (missingMethods.length > 0 || extraMethods.length > 0) {
        methodMismatches.push({
          route,
          missingInSpec: missingMethods,
          missingInCode: extraMethods,
        });
      }
    }
  }

  // Check spec paths against code
  for (const [route, methods] of specPaths) {
    if (!codeEndpoints.has(route)) {
      missingInCode.push({ route, methods });
    }
  }

  // Report results
  let hasErrors = false;

  if (missingInSpec.length > 0) {
    hasErrors = true;
    console.log('❌ Routes in code but NOT in openapi.yaml:');
    for (const { route, methods } of missingInSpec) {
      console.log(`   ${route} [${methods.join(', ')}]`);
    }
    console.log('');
  }

  if (missingInCode.length > 0) {
    hasErrors = true;
    console.log('❌ Routes in openapi.yaml but NOT in code:');
    for (const { route, methods } of missingInCode) {
      console.log(`   ${route} [${methods.join(', ')}]`);
    }
    console.log('');
  }

  if (methodMismatches.length > 0) {
    hasErrors = true;
    console.log('❌ Method mismatches:');
    for (const { route, missingInSpec, missingInCode } of methodMismatches) {
      if (missingInSpec.length > 0) {
        console.log(
          `   ${route}: methods [${missingInSpec.join(', ')}] in code but not in spec`
        );
      }
      if (missingInCode.length > 0) {
        console.log(
          `   ${route}: methods [${missingInCode.join(', ')}] in spec but not in code`
        );
      }
    }
    console.log('');
  }

  if (hasErrors) {
    console.log('💡 Please update openapi.yaml to match your API endpoints.\n');
    process.exit(1);
  } else {
    console.log(
      `✅ All ${codeEndpoints.size} API routes are properly documented in openapi.yaml\n`
    );
    process.exit(0);
  }
}

validate();
