/**
 * utils.js - Shared Utilities Module
 *
 * Provides common functionality:
 * - DOM utilities (escapeHtml, $, $$)
 * - WebSocket management
 * - State management
 * - Animation utilities
 * - Debug/logging utilities
 */

const LoupGarouUtils = (function() {
    'use strict';

    // ============================================
    // State
    // ============================================

    const state = {
        ws: null,
        wsReady: false,
        gameState: null,
        players: [],
        selectedTarget: null,
        debugMode: true, // Toggle this to enable/disable debug features
    };

    // ============================================
    // DOM Utilities
    // ============================================

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Shorthand for document.getElementById
     * @param {string} id - Element ID
     * @returns {HTMLElement|null}
     */
    function $(id) {
        return document.getElementById(id);
    }

    /**
     * Shorthand for document.querySelectorAll
     * @param {string} selector - CSS selector
     * @param {HTMLElement} parent - Parent element (default: document)
     * @returns {NodeList}
     */
    function $$(selector, parent = document) {
        return parent.querySelectorAll(selector);
    }

    /**
     * Create an element with attributes and children
     * @param {string} tag - HTML tag name
     * @param {Object} attrs - Attributes object
     * @param {Array} children - Child elements or strings
     * @returns {HTMLElement}
     */
    function createElement(tag, attrs = {}, children = []) {
        const el = document.createElement(tag);

        Object.keys(attrs).forEach(key => {
            if (key === 'className') {
                el.className = attrs[key];
            } else if (key === 'dataset') {
                Object.keys(attrs.dataset).forEach(dataKey => {
                    el.dataset[dataKey] = attrs.dataset[dataKey];
                });
            } else if (key.startsWith('on')) {
                el.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
            } else {
                el.setAttribute(key, attrs[key]);
            }
        });

        children.forEach(child => {
            if (typeof child === 'string') {
                el.appendChild(document.createTextNode(child));
            } else if (child instanceof Node) {
                el.appendChild(child);
            }
        });

        return el;
    }

    // ============================================
    // WebSocket Utilities
    // ============================================

    /**
     * Create WebSocket connection with auto-reconnect
     * @param {string} path - WebSocket path (e.g., '/loup_garou/ws')
     * @param {Object} handlers - Event handlers { onOpen, onMessage, onError, onClose }
     * @returns {WebSocket}
     */
    function createWebSocket(path, handlers = {}) {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}${path}`;
        const ws = new WebSocket(url);

        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        const baseDelay = 1000;

        ws.onopen = (event) => {
            state.wsReady = true;
            reconnectAttempts = 0;
            if (handlers.onOpen) handlers.onOpen(event);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (handlers.onMessage) handlers.onMessage(data);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.onerror = (event) => {
            if (handlers.onError) handlers.onError(event);
        };

        ws.onclose = (event) => {
            state.wsReady = false;
            if (handlers.onClose) handlers.onClose(event);

            // Auto-reconnect
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = baseDelay * Math.pow(2, reconnectAttempts - 1);
                setTimeout(() => {
                    console.log(`Reconnecting... (attempt ${reconnectAttempts})`);
                    createWebSocket(path, handlers);
                }, delay);
            }
        };

        state.ws = ws;
        return ws;
    }

    /**
     * Send message via WebSocket
     * @param {string} type - Message type
     * @param {Object} data - Message data
     */
    function wsSend(type, data = {}) {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type, ...data }));
        } else {
            console.warn('WebSocket not connected');
        }
    }

    /**
     * Check if WebSocket is connected
     * @returns {boolean}
     */
    function isWsConnected() {
        return state.ws && state.ws.readyState === WebSocket.OPEN;
    }

    // ============================================
    // Animation Utilities
    // ============================================

    /**
     * Add animation class and remove after completion
     * @param {HTMLElement} el - Element to animate
     * @param {string} animationClass - CSS animation class
     * @param {number} duration - Duration in ms (optional, auto-detected)
     */
    function animateOnce(el, animationClass, duration) {
        if (!el) return;

        // Get animation duration from CSS if not provided
        if (!duration) {
            const style = getComputedStyle(el);
            duration = parseFloat(style.animationDuration) * 1000;
        }

        el.classList.add(animationClass);
        setTimeout(() => {
            el.classList.remove(animationClass);
        }, duration);
    }

    /**
     * Show element with animation
     * @param {HTMLElement} el - Element to show
     * @param {string} animation - Animation class (default: 'animate-slide-up')
     */
    function showWithAnimation(el, animation = 'animate-slide-up') {
        if (!el) return;
        el.classList.remove('hidden');
        animateOnce(el, animation);
    }

    /**
     * Hide element with animation
     * @param {HTMLElement} el - Element to hide
     */
    function hideWithAnimation(el) {
        if (!el) return;
        el.classList.add('hidden');
    }

    /**
     * Toggle element visibility
     * @param {HTMLElement} el - Element to toggle
     */
    function toggleVisibility(el) {
        if (!el) return;
        el.classList.toggle('hidden');
    }

    // ============================================
    // Debug Utilities
    // ============================================

    /**
     * Debug logging
     * @param {string} msg - Message
     * @param {string} type - Log type ('log', 'info', 'warn', 'error')
     */
    function debugLog(msg, type = 'log') {
        if (!state.debugMode) return;

        const timestamp = new Date().toLocaleTimeString('fr-FR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const logFn = console[type] || console.log;
        logFn(`[${timestamp}] ${msg}`);
    }

    /**
     * Get debug mode status
     * @returns {boolean}
     */
    function isDebugMode() {
        return state.debugMode;
    }

    /**
     * Toggle debug mode
     * @param {boolean} enabled - Enable/disable
     */
    function setDebugMode(enabled) {
        state.debugMode = !!enabled;
    }

    // ============================================
    // Public API
    // ============================================

    return {
        // State (read-only access)
        getState: () => ({ ...state }),

        // DOM utilities
        escapeHtml,
        $,
        $$,
        createElement,

        // WebSocket utilities
        createWebSocket,
        wsSend,
        isWsConnected,

        // Animation utilities
        animateOnce,
        showWithAnimation,
        hideWithAnimation,
        toggleVisibility,

        // Debug utilities
        debugLog,
        isDebugMode,
        setDebugMode,
    };
})();