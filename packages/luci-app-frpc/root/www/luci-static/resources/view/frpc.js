'use strict';
'require view';
'require form';
'require rpc';
'require ui';
'require uci';
'require poll';
'require dom';
'require fs';
'require tools.widgets as widgets';

const callManagerStatus = rpc.declare({
	object: 'frpc-manager',
	method: 'status',
	expect: { '': {} }
});

const callManagerLogs = rpc.declare({
	object: 'frpc-manager',
	method: 'logs',
	expect: { '': {} }
});

const callClearLogs = rpc.declare({
	object: 'frpc-manager',
	method: 'clear_logs',
	expect: { '': {} }
});

const callManagerAction = rpc.declare({
	object: 'frpc-manager',
	method: 'action',
	params: [ 'action' ],
	expect: { '': {} }
});

const callReadRaw = rpc.declare({
	object: 'frpc-manager',
	method: 'read_raw',
	params: [ 'format' ],
	expect: { '': {} }
});

const callSaveRaw = rpc.declare({
	object: 'frpc-manager',
	method: 'save_raw',
	params: [ 'format', 'content' ],
	expect: { '': {} }
});

const callUseUci = rpc.declare({
	object: 'frpc-manager',
	method: 'use_uci',
	expect: { '': {} }
});

const callInstallCore = rpc.declare({
	object: 'frpc-manager',
	method: 'install_core',
	expect: { '': {} }
});

const callRestoreCore = rpc.declare({
	object: 'frpc-manager',
	method: 'restore_core',
	expect: { '': {} }
});

const pageStyle = [
	'.frpc-runtime-toolbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; }',
	'.frpc-runtime-actions { display:flex; align-items:center; gap:.6rem; min-height:2.4rem; }',
	'.frpc-runtime-statuses { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; }',
	'.frpc-runtime-state { display:flex; align-items:center; gap:.55rem; font-weight:600; }',
	'.frpc-state-dot { width:.72rem; height:.72rem; border-radius:50%; background:#8b949e; display:inline-block; flex:0 0 auto; }',
	'.frpc-state-dot.running { background:#2da44e; }',
	'.frpc-state-dot.stopped { background:#cf222e; }',
	'.frpc-log { box-sizing:border-box; height:18rem; max-height:18rem; overflow:auto; margin:0; padding:.8rem; border:1px solid var(--border-color-medium, #d8dee4); border-radius:4px; background:var(--background-color-low, #f6f8fa); color:var(--text-color-high, #24292f); white-space:pre-wrap; word-break:break-word; font:12px/1.55 monospace; }',
	'.frpc-log-toolbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:.25rem 0 .65rem; }',
	'.frpc-log-toolbar h3 { margin:0; font-size:1rem; }',
	'.frpc-editor { box-sizing:border-box; width:100%; min-height:25rem; max-height:25rem; resize:vertical; font:12px/1.55 monospace; }',
	'.frpc-panel-toolbar { display:flex; align-items:center; gap:.7rem; flex-wrap:wrap; margin:.5rem 0 1rem; }',
	'.frpc-panel-toolbar select { min-width:8rem; }',
	'.frpc-meta { display:grid; grid-template-columns:minmax(8rem, 11rem) minmax(0, 1fr); gap:.55rem 1rem; margin:0 0 1rem; }',
	'.frpc-meta dt { font-weight:600; }',
	'.frpc-meta dd { margin:0; min-width:0; overflow-wrap:anywhere; font-family:monospace; }',
	'.frpc-meta-value { display:flex; align-items:center; gap:.65rem; flex-wrap:wrap; }',
	'.frpc-subcard { margin:0 0 1rem; padding:1rem; border:1px solid var(--border-color-medium, #d8dee4); border-radius:4px; }',
	'.frpc-subcard h3 { margin:0 0 .8rem; font-size:1rem; }',
	'.frpc-mode { font-weight:600; margin-left:auto; }',
	'.cbi-value-description { display:none; }',
	'.cbi-tabmenu { display:flex; flex-wrap:nowrap; overflow-x:auto; white-space:nowrap; }',
	'.cbi-tabmenu > li { flex:0 0 auto; }',
	'@media (max-width:600px) { .frpc-meta { grid-template-columns:1fr; gap:.2rem; } .frpc-meta dd { margin-bottom:.55rem; } .frpc-mode { width:100%; margin-left:0; } }'
].join('\n');

const serverOptions = [
	[ form.Value, 'server_addr', _('Server address'), _('Address of the frps server.'), { datatype: 'host', rmempty: false } ],
	[ form.Value, 'server_port', _('Server port'), _('Port of the frps server.'), { datatype: 'port', placeholder: '7000', rmempty: false } ],
	[ form.ListValue, 'protocol', _('Transport protocol'), _('Protocol used to connect to the frps server.'), { values: [ [ 'tcp', 'TCP' ], [ 'kcp', 'KCP' ], [ 'quic', 'QUIC' ], [ 'websocket', 'WebSocket' ], [ 'wss', 'WebSocket TLS' ] ], default: 'tcp' } ],
	[ form.Flag, 'tls_enable', _('Enable TLS'), _('Encrypt the connection between frpc and frps.'), { datatype: 'bool', default: 'true' } ],
	[ form.Value, 'tls_server_name', _('TLS server name'), _('Server name used for TLS certificate verification.') ],
	[ form.Flag, 'disable_custom_tls_first_byte', _('Disable custom TLS first byte'), _('Use a standard TLS handshake without the frp custom first byte.'), { datatype: 'bool', default: 'false' } ],
	[ form.Value, 'token', _('Authentication token'), _('Token shared with the frps server.'), { password: true } ],
	[ form.Value, 'user', _('User prefix'), _('Prefix used to distinguish proxy names from other clients.') ],
	[ form.Flag, 'login_fail_exit', _('Exit after login failure'), _('Stop the process after a failed login instead of retrying.'), { datatype: 'bool', default: 'true' } ],
	[ form.Value, 'http_proxy', _('HTTP proxy'), _('HTTP or SOCKS5 proxy used to connect to the frps server.'), { placeholder: 'http://127.0.0.1:8080' } ],
	[ form.Value, 'dns_server', _('DNS server'), _('DNS server used by frpc.'), { datatype: 'ipaddr' } ]
];

const transportOptions = [
	[ form.Value, 'pool_count', _('Connection pool size'), _('Number of pre-established connections kept by the client.'), { datatype: 'uinteger', placeholder: '0' } ],
	[ form.Flag, 'tcp_mux', _('TCP multiplexing'), _('Share one TCP connection between multiple proxy requests.'), { datatype: 'bool', default: 'true' } ],
	[ form.Value, 'tcp_mux_keepalive_interval', _('TCP mux keepalive interval'), _('Keepalive interval in seconds for multiplexed connections.'), { datatype: 'uinteger', placeholder: '30' } ],
	[ form.Value, 'dial_server_timeout', _('Dial timeout'), _('Maximum time in seconds to establish a server connection.'), { datatype: 'uinteger', placeholder: '10' } ],
	[ form.Value, 'dial_server_keepalive', _('Dial keepalive'), _('TCP keepalive interval in seconds for server connections.'), { datatype: 'uinteger', placeholder: '7200' } ],
	[ form.Value, 'connect_server_local_ip', _('Source IP'), _('Local source address used to connect to the server.'), { datatype: 'ipaddr' } ],
	[ form.Value, 'heartbeat_interval', _('Heartbeat interval'), _('Heartbeat interval in seconds.'), { datatype: 'uinteger', placeholder: '30' } ],
	[ form.Value, 'heartbeat_timeout', _('Heartbeat timeout'), _('Heartbeat timeout in seconds.'), { datatype: 'uinteger', placeholder: '90' } ]
];

const webManagementOptions = [
	[ form.Value, 'admin_addr', _('Web management address'), _('Address of the local frpc web management interface.'), { datatype: 'ipaddr', placeholder: '127.0.0.1' } ],
	[ form.Value, 'admin_port', _('Web management port'), _('Port of the local frpc web management interface.'), { datatype: 'port' } ],
	[ form.Value, 'admin_user', _('Web management user') ],
	[ form.Value, 'admin_pwd', _('Web management password'), undefined, { password: true } ],
	[ form.Value, 'assets_dir', _('Web assets directory') ],
	[ form.Flag, 'pprof_enable', _('Enable pprof'), _('Expose Go pprof endpoints on the web management interface.'), { datatype: 'bool', default: 'false' } ]
];

const loggingOptions = [
	[ form.Value, 'log_file', _('Log file'), _('Use console for system log output, or specify an absolute file path.'), { placeholder: 'console' } ],
	[ form.ListValue, 'log_level', _('Log level'), undefined, { values: [ 'trace', 'debug', 'info', 'warn', 'error' ], default: 'info' } ],
	[ form.Value, 'log_max_days', _('Log retention days'), _('Maximum number of days to retain log files.'), { datatype: 'uinteger', placeholder: '3' } ],
	[ form.Flag, 'disable_log_color', _('Disable log colors'), _('Disable ANSI colors in console output.'), { datatype: 'bool', default: 'true' } ]
];

const rawIniOptions = [
	[ form.DynamicList, '_', _('Additional INI settings'), _('Extra key=value entries written to the common section.'), { placeholder: 'key = value' } ]
];

const startupOptions = [
	[ form.Flag, 'stdout', _('Capture stdout'), undefined, { default: '1' } ],
	[ form.Flag, 'stderr', _('Capture stderr'), undefined, { default: '1' } ],
	[ widgets.UserSelect, 'user', _('Run as user') ],
	[ widgets.GroupSelect, 'group', _('Run as group') ],
	[ form.Flag, 'respawn', _('Automatic restart'), _('Restart frpc automatically after an unexpected exit.'), { default: '1' } ],
	[ form.DynamicList, 'env', _('Environment variables'), _('Environment variables passed to frpc configuration templates.'), { placeholder: 'NAME=value' } ],
	[ form.DynamicList, 'conf_inc', _('Additional INI files'), _('INI files appended to the generated page configuration.'), { placeholder: '/etc/frp/extra.ini' } ]
];

const proxyGeneralOptions = [
	[ form.Flag, 'use_encryption', _('Enable encryption'), _('Encrypt traffic between frpc and frps.'), { datatype: 'bool', default: 'false' } ],
	[ form.Flag, 'use_compression', _('Enable compression'), _('Compress traffic between frpc and frps.'), { datatype: 'bool', default: 'false' } ],
	[ form.Value, 'bandwidth_limit', _('Bandwidth limit'), _('Per-proxy bandwidth limit, for example 10MB or 1MB.'), { placeholder: '10MB' } ],
	[ form.ListValue, 'bandwidth_limit_mode', _('Bandwidth limit mode'), undefined, { values: [ [ 'client', _('Client') ], [ 'server', _('Server') ] ], default: 'client' } ],
	[ form.ListValue, 'proxy_protocol_version', _('Proxy Protocol'), undefined, { values: [ [ '', _('Disabled') ], [ 'v1', 'v1' ], [ 'v2', 'v2' ] ] } ],
	[ form.Value, 'group', _('Load balancing group') ],
	[ form.Value, 'group_key', _('Load balancing key'), undefined, { password: true } ]
];

const proxyHttpOptions = [
	[ form.Value, 'custom_domains', _('Custom domains'), _('Comma-separated domain names.') ],
	[ form.Value, 'subdomain', _('Subdomain') ],
	[ form.Value, 'locations', _('URL locations'), _('Comma-separated URL prefixes.') ],
	[ form.Value, 'http_user', _('HTTP basic user') ],
	[ form.Value, 'http_pwd', _('HTTP basic password'), undefined, { password: true } ],
	[ form.Value, 'host_header_rewrite', _('Host header rewrite') ],
	[ form.Value, 'route_by_http_user', _('Route by HTTP user') ],
	[ form.Value, 'multiplexer', _('TCP multiplexer'), undefined, { placeholder: 'httpconnect' } ]
];

const proxyVisitorOptions = [
	[ form.ListValue, 'role', _('Role'), undefined, { values: [ [ 'server', _('Server') ], [ 'visitor', _('Visitor') ] ] } ],
	[ form.Value, 'server_name', _('Server proxy name'), undefined, { depends: { role: 'visitor' } } ],
	[ form.Value, 'bind_addr', _('Visitor bind address'), undefined, { datatype: 'ipaddr', depends: { role: 'visitor' }, placeholder: '127.0.0.1' } ],
	[ form.Value, 'bind_port', _('Visitor bind port'), undefined, { datatype: 'port', depends: { role: 'visitor' } } ],
	[ form.Value, 'sk', _('Secret key'), undefined, { password: true } ],
	[ form.Value, 'server_user', _('Server user'), undefined, { depends: { role: 'visitor' } } ]
];

const proxyHealthOptions = [
	[ form.ListValue, 'health_check_type', _('Health check type'), undefined, { values: [ [ '', _('Disabled') ], [ 'tcp', 'TCP' ], [ 'http', 'HTTP' ] ] } ],
	[ form.Value, 'health_check_url', _('Health check URL'), undefined, { depends: { health_check_type: 'http' }, placeholder: '/status' } ],
	[ form.Value, 'health_check_timeout_s', _('Health check timeout'), undefined, { datatype: 'uinteger', placeholder: '3' } ],
	[ form.Value, 'health_check_max_failed', _('Health check failure threshold'), undefined, { datatype: 'uinteger', placeholder: '1' } ],
	[ form.Value, 'health_check_interval_s', _('Health check interval'), undefined, { datatype: 'uinteger', placeholder: '10' } ]
];

const proxyPluginOptions = [
	[ form.ListValue, 'plugin', _('Plugin'), undefined, { values: [ [ '', _('Disabled') ], [ 'http_proxy', 'HTTP Proxy' ], [ 'socks5', 'SOCKS5' ], [ 'unix_domain_socket', 'Unix Domain Socket' ] ] } ],
	[ form.Value, 'plugin_http_user', _('HTTP proxy user'), undefined, { depends: { plugin: 'http_proxy' } } ],
	[ form.Value, 'plugin_http_passwd', _('HTTP proxy password'), undefined, { password: true, depends: { plugin: 'http_proxy' } } ],
	[ form.Value, 'plugin_user', _('SOCKS5 user'), undefined, { depends: { plugin: 'socks5' } } ],
	[ form.Value, 'plugin_passwd', _('SOCKS5 password'), undefined, { password: true, depends: { plugin: 'socks5' } } ],
	[ form.Value, 'plugin_unix_path', _('Unix socket path'), undefined, { depends: { plugin: 'unix_domain_socket' }, datatype: 'file', placeholder: '/var/run/docker.sock' } ]
];

const proxyAdvancedOptions = [
	[ form.DynamicList, '_', _('Additional proxy settings'), _('Extra key=value entries written to this proxy section.'), { placeholder: 'key = value' } ]
];

let runtimeState = {};
let runtimePollRegistered = false;
let normalizeClientProxiesLock = null;

function setParams(option, params) {
	if (!params)
		return;

	for (let key in params) {
		let value = params[key];

		if (key === 'values') {
			for (let item of value)
				option.value.apply(option, Array.isArray(item) ? item : [ item ]);
		}
		else if (key === 'depends') {
			let dependencies = Array.isArray(value) ? value : [ value ];
			let existing = option.deps && option.deps.length ? option.deps : [ {} ];
			let merged = [];
			for (let dependency of dependencies)
				for (let current of existing)
					merged.push(Object.assign({}, current, dependency));
			option.deps = merged;
		}
		else {
			option[key] = value;
		}
	}

	if (params.datatype === 'bool') {
		option.enabled = 'true';
		option.disabled = 'false';
	}
}

function addTabOptions(section, tab, options, defaults) {
	for (let item of options) {
		let option = section.taboption(tab, item[0], item[1], item[2], item[3]);
		setParams(option, item[4]);
		setParams(option, defaults);
	}
}

function addOptions(section, options) {
	for (let item of options) {
		let option = section.option(item[0], item[1], item[2], item[3]);
		setParams(option, item[4]);
	}
}

function ensureSuccess(result) {
	if (!result || result.success === false || result.success === 0)
		throw new Error(result && result.error ? result.error : _('Operation failed'));
	return result;
}

function notifyError(error) {
	ui.addNotification(null, E('p', {}, error.message || String(error)), 'error');
}

function cleanLog(text) {
	return String(text || '').replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
}

function formatSize(bytes) {
	let value = Number(bytes || 0);
	if (value < 1024)
		return '%d B'.format(value);
	if (value < 1024 * 1024)
		return '%.1f KiB'.format(value / 1024);
	return '%.2f MiB'.format(value / 1024 / 1024);
}

function updateRuntimeDom(status, logs) {
	runtimeState = status || runtimeState;
	let running = !!runtimeState.running;
	let button = document.getElementById('frpc-toggle-service');
	let state = document.getElementById('frpc-runtime-state');
	let dot = document.getElementById('frpc-state-dot');
	let log = document.getElementById('frpc-log');
	let autostart = document.getElementById('frpc-autostart-state');

	if (button) {
		button.textContent = running ? _('Stop service') : _('Start service');
		button.className = 'cbi-button ' + (running ? 'cbi-button-negative' : 'cbi-button-action');
		button.disabled = false;
	}
	if (state)
		state.textContent = running ? _('Running') : _('Stopped');
	if (dot)
		dot.className = 'frpc-state-dot ' + (running ? 'running' : 'stopped');
	if (log && logs)
		log.textContent = cleanLog(logs.logs) || _('No frpc logs yet.');
	if (autostart)
		autostart.textContent = runtimeState.enabled ? _('Starts at boot') : _('Disabled at boot');

	updateCoreDom(runtimeState);
}

function refreshRuntime() {
	return Promise.all([
		L.resolveDefault(callManagerStatus(), {}),
		L.resolveDefault(callManagerLogs(), {})
	]).then(function(result) {
		updateRuntimeDom(result[0], result[1]);
	});
}

function handleServiceToggle(event) {
	event.preventDefault();
	let button = event.currentTarget;
	let action = runtimeState.running ? 'stop' : 'start';
	button.disabled = true;
	button.textContent = _('Please wait...');

	return callManagerAction(action).then(ensureSuccess).then(function() {
		return refreshRuntime();
	}).catch(function(error) {
		button.disabled = false;
		notifyError(error);
	});
}

function handleClearLogs(event) {
	event.preventDefault();
	ui.showModal(_('Clear frpc logs'), [
		E('p', {}, _('Clear old frpc log entries and configured frpc log files? Other system logs will not be affected.')),
		E('div', { class: 'right' }, [
			E('button', {
				type: 'button',
				class: 'cbi-button',
				click: function() { ui.hideModal(); }
			}, _('Cancel')),
			' ',
			E('button', {
				type: 'button',
				class: 'cbi-button cbi-button-negative',
				click: function(clearEvent) {
					let button = clearEvent.currentTarget;
					button.disabled = true;
					return callClearLogs().then(ensureSuccess).then(function() {
						ui.hideModal();
						ui.addNotification(null, E('p', {}, _('frpc logs cleared.')));
						return refreshRuntime();
					}).catch(function(error) {
						button.disabled = false;
						notifyError(error);
					});
				}
			}, _('Clear logs'))
		])
	]);
}

function renderRuntimePanel() {
	let panel = E('div', {}, [
		E('div', { class: 'frpc-runtime-toolbar' }, [
			E('div', { class: 'frpc-runtime-actions' }, [
				E('button', {
					id: 'frpc-toggle-service',
					type: 'button',
					class: 'cbi-button cbi-button-action',
					click: handleServiceToggle
				}, _('Please wait...'))
			]),
			E('div', { class: 'frpc-runtime-statuses' }, [
				E('div', { class: 'frpc-runtime-state' }, [
					E('span', { id: 'frpc-state-dot', class: 'frpc-state-dot' }),
					E('span', { id: 'frpc-runtime-state' }, _('Loading...'))
				]),
				E('span', { id: 'frpc-autostart-state' }, _('Loading...'))
			])
		]),
		E('div', { class: 'frpc-log-toolbar' }, [
			E('h3', {}, _('Logs')),
			E('button', {
				id: 'frpc-clear-logs',
				type: 'button',
				class: 'cbi-button cbi-button-negative',
				click: handleClearLogs
			}, _('Clear logs'))
		]),
		E('pre', { id: 'frpc-log', class: 'frpc-log' }, _('Loading logs...'))
	]);

	window.setTimeout(refreshRuntime, 0);
	if (!runtimePollRegistered) {
		runtimePollRegistered = true;
		poll.add(refreshRuntime);
	}
	return panel;
}

function loadRawEditor(format, editor, pathNode) {
	editor.disabled = true;
	pathNode.textContent = _('Loading...');
	return callReadRaw(format).then(ensureSuccess).then(function(result) {
		editor.value = result.content || '';
		pathNode.textContent = result.path || '';
	}).catch(notifyError).finally(function() {
		editor.disabled = false;
	});
}

function renderRawPanel() {
	let format = E('select', {}, [
		E('option', { value: 'toml' }, 'TOML'),
		E('option', { value: 'ini' }, 'INI')
	]);
	format.value = runtimeState.config_mode === 'raw' ? (runtimeState.raw_format || 'toml') : 'ini';
	let editor = E('textarea', {
		class: 'cbi-input-textarea frpc-editor',
		spellcheck: 'false',
		wrap: 'off'
	});
	let path = E('span', { class: 'frpc-mode' }, '');
	let saveButton = E('button', {
		type: 'button',
		class: 'cbi-button cbi-button-action'
	}, _('Save and use raw configuration'));
	let uciButton = E('button', {
		type: 'button',
		class: 'cbi-button'
	}, _('Use page configuration'));

	format.addEventListener('change', function() {
		loadRawEditor(format.value, editor, path);
	});
	saveButton.addEventListener('click', function(event) {
		event.preventDefault();
		saveButton.disabled = true;
		return callSaveRaw(format.value, editor.value).then(ensureSuccess).then(function(result) {
			ui.addNotification(null, E('p', {}, result.running ? _('Raw configuration saved and frpc restarted.') : _('Raw configuration saved, but frpc is not running.')));
			return refreshRuntime();
		}).catch(notifyError).finally(function() {
			saveButton.disabled = false;
		});
	});
	uciButton.addEventListener('click', function(event) {
		event.preventDefault();
		uciButton.disabled = true;
		return callUseUci().then(ensureSuccess).then(function(result) {
			ui.addNotification(null, E('p', {}, result.running ? _('Page configuration enabled and frpc restarted.') : _('Page configuration enabled, but frpc is not running.')));
			return refreshRuntime();
		}).catch(notifyError).finally(function() {
			uciButton.disabled = false;
		});
	});

	window.setTimeout(function() {
		loadRawEditor(format.value, editor, path);
	}, 0);

	return E('fieldset', { class: 'cbi-section frpc-subcard' }, [
		E('h3', {}, _('Raw configuration editor')),
		E('div', { class: 'frpc-panel-toolbar' }, [ format, saveButton, uciButton, path ]),
		editor
	]);
}

function downloadCore(path, filename) {
	return fs.read_direct(path, 'blob').then(function(blob) {
		let url = URL.createObjectURL(blob);
		let link = E('a', { href: url, download: filename, style: 'display:none' });
		document.body.appendChild(link);
		link.click();
		link.remove();
		window.setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
	}).catch(notifyError);
}

function updateCoreDom(status) {
	let fields = {
		'frpc-core-version': status.version || _('Unknown'),
		'frpc-core-size': formatSize(status.size),
		'frpc-core-sha256': status.sha256 || '-',
		'frpc-core-backup': status.backup_version || _('None')
	};
	for (let id in fields) {
		let node = document.getElementById(id);
		if (node)
			node.textContent = fields[id];
	}
	let restore = document.getElementById('frpc-restore-core');
	if (restore)
		restore.disabled = !status.backup_version;
	let downloadBackup = document.getElementById('frpc-download-backup');
	if (downloadBackup)
		downloadBackup.disabled = !status.backup_version;
}

function renderCorePanel() {
	let uploadButton = E('button', {
		type: 'button',
		class: 'cbi-button cbi-button-action'
	}, _('Upload and replace core'));
	let restoreButton = E('button', {
		id: 'frpc-restore-core',
		type: 'button',
		class: 'cbi-button',
		disabled: !runtimeState.backup_version
	}, _('Restore backup core'));
	let downloadCurrentButton = E('button', {
		id: 'frpc-download-current',
		type: 'button',
		class: 'cbi-button'
	}, _('Download'));
	let downloadBackupButton = E('button', {
		id: 'frpc-download-backup',
		type: 'button',
		class: 'cbi-button',
		disabled: !runtimeState.backup_version
	}, _('Download'));

	uploadButton.addEventListener('click', function(event) {
		event.preventDefault();
		return ui.uploadFile('/tmp/frpc-core-upload').then(function() {
			ui.showModal(_('Replacing frpc core'), [ E('p', { class: 'spinning' }, _('Validating and replacing the uploaded core...')) ]);
			return callInstallCore();
		}).then(ensureSuccess).then(function(result) {
			ui.addNotification(null, E('p', {}, result.message || _('frpc core replaced.')));
			return refreshRuntime();
		}).catch(notifyError).finally(function() {
			ui.hideModal();
		});
	});
	restoreButton.addEventListener('click', function(event) {
		event.preventDefault();
		restoreButton.disabled = true;
		return callRestoreCore().then(ensureSuccess).then(function(result) {
			ui.addNotification(null, E('p', {}, result.message || _('Backup core restored.')));
			return refreshRuntime();
		}).catch(notifyError).finally(function() {
			restoreButton.disabled = false;
		});
	});
	downloadCurrentButton.addEventListener('click', function(event) {
		event.preventDefault();
		return downloadCore('/usr/bin/frpc', 'frpc');
	});
	downloadBackupButton.addEventListener('click', function(event) {
		event.preventDefault();
		return downloadCore('/usr/libexec/frpc-core.backup', 'frpc-backup');
	});

	window.setTimeout(function() { updateCoreDom(runtimeState); }, 0);
	return E('div', {}, [
		E('dl', { class: 'frpc-meta' }, [
			E('dt', {}, _('Current version')), E('dd', { class: 'frpc-meta-value' }, [ E('span', { id: 'frpc-core-version' }, runtimeState.version || _('Loading...')), downloadCurrentButton ]),
			E('dt', {}, _('Core path')), E('dd', {}, '/usr/bin/frpc'),
			E('dt', {}, _('Core size')), E('dd', { id: 'frpc-core-size' }, formatSize(runtimeState.size)),
			E('dt', {}, 'SHA256'), E('dd', { id: 'frpc-core-sha256' }, runtimeState.sha256 || '-'),
			E('dt', {}, _('Backup version')), E('dd', { class: 'frpc-meta-value' }, [ E('span', { id: 'frpc-core-backup' }, runtimeState.backup_version || _('None')), downloadBackupButton ])
		]),
		E('div', { class: 'frpc-panel-toolbar' }, [ uploadButton, restoreButton ])
	]);
}

function stripProxyProtocolSuffix(name) {
	return String(name || '').replace(/_(tcp|udp|http|https|stcp|xtcp|tcpmux|sudp)$/i, '');
}

function makeProxyName(name, type) {
	let supported = [ 'tcp', 'udp', 'http', 'https', 'stcp', 'xtcp', 'tcpmux', 'sudp' ];
	let base = stripProxyProtocolSuffix(name);
	if (!base)
		base = 'proxy';
	return supported.indexOf(type) >= 0 ? '%s_%s'.format(base, type) : base;
}

function snapshotProxyOptions(section) {
	let data = {};
	for (let key in section)
		if (key.charAt(0) !== '.')
			data[key] = section[key];
	return data;
}

function findProxySection(name, type) {
	for (let section of (uci.sections('frpc', 'conf') || [])) {
		if (section['.name'] !== 'common' && section.name === name && section.type === type)
			return section['.name'];
	}
	return null;
}

function writeProxyOptions(sectionId, source, type, name) {
	for (let key in source)
		if (key !== 'name' && key !== 'type')
			uci.set('frpc', sectionId, key, source[key]);
	uci.set('frpc', sectionId, 'type', type);
	uci.set('frpc', sectionId, 'name', name);
}

function removeDuplicateProxySections() {
	let seen = {};
	let supported = [ 'tcp', 'udp', 'http', 'https', 'stcp', 'xtcp', 'tcpmux', 'sudp' ];
	for (let section of (uci.sections('frpc', 'conf') || [])) {
		let sectionId = section['.name'];
		if (sectionId === 'common' || supported.indexOf(section.type) < 0)
			continue;
		let name = makeProxyName(section.name, section.type);
		let key = '%s:%s'.format(section.type, name);
		if (seen[key])
			uci.remove('frpc', sectionId);
		else {
			seen[key] = true;
			uci.set('frpc', sectionId, 'name', name);
		}
	}
}

function normalizeClientProxiesOnce() {
	let combined = [];
	let supported = [ 'tcp', 'udp', 'http', 'https', 'stcp', 'xtcp', 'tcpmux', 'sudp' ];
	for (let section of (uci.sections('frpc', 'conf') || [])) {
		let sectionId = section['.name'];
		if (sectionId === 'common')
			continue;
		let type = section.type || 'tcp';
		if (type === 'tcp_udp')
			combined.push({ sectionId: sectionId, data: snapshotProxyOptions(section) });
		else if (supported.indexOf(type) >= 0)
			uci.set('frpc', sectionId, 'name', makeProxyName(section.name, type));
	}

	for (let item of combined) {
		let source = item.data;
		uci.remove('frpc', item.sectionId);
		for (let type of [ 'tcp', 'udp' ]) {
			let name = makeProxyName(source.name, type);
			let sectionId = findProxySection(name, type) || uci.add('frpc', 'conf');
			writeProxyOptions(sectionId, source, type, name);
		}
	}
	removeDuplicateProxySections();
	return uci.save();
}

function normalizeClientProxies() {
	if (normalizeClientProxiesLock)
		return normalizeClientProxiesLock;
	normalizeClientProxiesLock = uci.load('frpc').then(normalizeClientProxiesOnce).finally(function() {
		normalizeClientProxiesLock = null;
	});
	return normalizeClientProxiesLock;
}

function configureProxyGrid(section) {
	let option;
	section.anonymous = true;
	section.addremove = true;
	section.sortable = true;
	section.addbtntitle = _('Add proxy');
	section.filter = function(sectionId) { return sectionId !== 'common'; };
	section.tab('general', _('General'));
	section.tab('http', _('HTTP and domains'));
	section.tab('visitor', _('Visitors'));
	section.tab('health', _('Health check'));
	section.tab('plugin', _('Plugin'));
	section.tab('advanced', _('Advanced'));

	option = section.taboption('general', form.Value, 'name', _('Proxy name'));
	option.rmempty = false;
	option.modalonly = false;
	option = section.taboption('general', form.ListValue, 'type', _('Proxy type'));
	for (let value of [ [ 'tcp', 'TCP' ], [ 'udp', 'UDP' ], [ 'tcp_udp', _('TCP and UDP') ], [ 'http', 'HTTP' ], [ 'https', 'HTTPS' ], [ 'stcp', 'STCP' ], [ 'xtcp', 'XTCP' ], [ 'tcpmux', 'TCPMUX' ], [ 'sudp', 'SUDP' ] ])
		option.value.apply(option, value);
	option.default = 'tcp';
	option.modalonly = false;
	option = section.taboption('general', form.Value, 'local_ip', _('Local address'));
	option.datatype = 'host';
	option.placeholder = '127.0.0.1';
	option.modalonly = false;
	option = section.taboption('general', form.Value, 'local_port', _('Local port'));
	option.datatype = 'port';
	option.modalonly = false;
	option = section.taboption('general', form.Value, 'remote_port', _('Remote port'));
	option.datatype = 'port';
	for (let type of [ 'tcp', 'udp', 'tcp_udp', 'sudp' ])
		option.depends('type', type);
	option.modalonly = false;
	option.cfgvalue = function() {
		let value = this.super('cfgvalue', arguments);
		return value && value !== '0' ? value : '#';
	};

	addTabOptions(section, 'general', proxyGeneralOptions, { optional: true, modalonly: true });
	addTabOptions(section, 'http', proxyHttpOptions, { optional: true, modalonly: true, depends: [ { type: 'http' }, { type: 'https' }, { type: 'tcpmux' } ] });
	addTabOptions(section, 'visitor', proxyVisitorOptions, { optional: true, modalonly: true, depends: [ { type: 'stcp' }, { type: 'xtcp' }, { type: 'sudp' } ] });
	addTabOptions(section, 'health', proxyHealthOptions, { optional: true, modalonly: true });
	addTabOptions(section, 'plugin', proxyPluginOptions, { optional: true, modalonly: true });
	addTabOptions(section, 'advanced', proxyAdvancedOptions, { optional: true, modalonly: true });
}

return view.extend({
	load: function() {
		return Promise.all([
			uci.load('frpc'),
			L.resolveDefault(callManagerStatus(), {})
		]);
	},

	render: function(data) {
		let map, section, option;
		runtimeState = data[1] || {};
		map = new form.Map('frpc', _('frp Client'));
		section = map.section(form.NamedSection, 'common', 'conf');
		section.dynamic = true;
		section.tab('runtime', _('Runtime'));
		section.tab('connection', _('Server configuration'));
		section.tab('transport', _('Transport configuration'));
		section.tab('security', _('Web management'));
		section.tab('logging', _('Logging'));
		section.tab('proxies', _('Port mappings'));
		section.tab('startup', _('Startup'));
		section.tab('raw', _('Raw configuration'));
		section.tab('core', _('Core management'));

		option = section.taboption('runtime', form.DummyValue, '_runtime');
		option.rawhtml = true;
		option.renderWidget = renderRuntimePanel;
		addTabOptions(section, 'connection', serverOptions, { optional: true });
		addTabOptions(section, 'transport', transportOptions, { optional: true });
		addTabOptions(section, 'security', webManagementOptions, { optional: true });
		addTabOptions(section, 'logging', loggingOptions, { optional: true });

		option = section.taboption('proxies', form.SectionValue, '_proxies', form.GridSection, 'conf');
		configureProxyGrid(option.subsection);

		option = section.taboption('startup', form.SectionValue, '_startup', form.TypedSection, 'init');
		option.subsection.anonymous = true;
		option.subsection.dynamic = true;
		addOptions(option.subsection, startupOptions);

		option = section.taboption('raw', form.SectionValue, '_raw_ini', form.TypedSection, 'conf', _('Additional INI settings'));
		option.subsection.anonymous = true;
		option.subsection.addremove = false;
		option.subsection.filter = function(sectionId) { return sectionId === 'common'; };
		addOptions(option.subsection, rawIniOptions);

		option = section.taboption('raw', form.DummyValue, '_raw');
		option.rawhtml = true;
		option.renderWidget = renderRawPanel;
		option = section.taboption('core', form.DummyValue, '_core');
		option.rawhtml = true;
		option.renderWidget = renderCorePanel;

		let originalSave = map.save.bind(map);
		map.save = function() {
			return originalSave.apply(this, arguments).then(normalizeClientProxies);
		};

		return map.render().then(function(node) {
			node.insertBefore(E('style', {}, pageStyle), node.firstChild);
			return node;
		});
	}
});
