'use strict';
'require view';
'require form';
'require rpc';
'require ui';
'require uci';
'require tools.widgets as widgets';

function frpT(text) {
	return _('frp Client') !== 'frp Client' ? _(text) : text;
}

function startupConf(name) {
	return [
		[ form.Flag, 'stdout', _('Log stdout') ],
		[ form.Flag, 'stderr', _('Log stderr') ],
		[ widgets.UserSelect, 'user', _('Run daemon as user') ],
		[ widgets.GroupSelect, 'group', _('Run daemon as group') ],
		[ form.Flag, 'respawn', _('Respawn when crashed') ],
		[ form.DynamicList, 'env', _('Environment variable'), _('OS environments pass to frp for config file template, see %s.'.format('<a href="https://github.com/fatedier/frp#configuration-file-template">frp README</a>')), { placeholder: 'ENV_NAME=value' } ],
		[ form.DynamicList, 'conf_inc', _('Additional INI configs'), _('INI config files include in temporary config file'), { placeholder: '/etc/config/%s_extra.ini'.format(name) } ]
	];
}

const clientCommonConf = [
	[ form.Value, 'server_addr', frpT('Server address'), _('ServerAddr specifies the address of the server to connect to.<br />By default, this value is "127.0.0.1".'), { datatype: 'host' } ],
	[ form.Value, 'server_port', _('Server port'), _('ServerPort specifies the port to connect to the server on.<br />By default, this value is 7000.'), { datatype: 'port' } ],
	[ form.Value, 'http_proxy', _('HTTP proxy'), _('HttpProxy specifies a proxy address to connect to the server through. If this value is "", the server will be connected to directly.<br />By default, this value is read from the "http_proxy" environment variable.') ],
	[ form.Value, 'log_file', _('Log file'), _('LogFile specifies a file where logs will be written to. This value will only be used if LogWay is set appropriately.<br />By default, this value is "console".') ],
	[ form.ListValue, 'log_level', frpT('Log level'), _('LogLevel specifies the minimum log level. Valid values are "trace", "debug", "info", "warn", and "error".<br />By default, this value is "info".'), { values: [ 'trace', 'debug', 'info', 'warn', 'error' ] } ],
	[ form.Value, 'log_max_days', _('Log max days'), _('LogMaxDays specifies the maximum number of days to store log information before deletion. This is only used if LogWay == "file".<br />By default, this value is 0.'), { datatype: 'uinteger' } ],
	[ form.Flag, 'disable_log_color', _('Disable log color'), _('DisableLogColor disables log colors when LogWay == "console" when set to true.'), { datatype: 'bool', default: 'false' } ],
	[ form.Value, 'token', _('Token'), _('Token specifies the authorization token used to create keys to be sent to the server. The server must have a matching token for authorization to succeed. <br />By default, this value is "".') ],
	[ form.Value, 'admin_addr', _('Admin address'), _('AdminAddr specifies the address that the admin server binds to.<br />By default, this value is "0.0.0.0".'), { datatype: 'ipaddr' } ],
	[ form.Value, 'admin_port', _('Admin port'), _('AdminPort specifies the port for the admin server to listen on. If this value is 0, the admin server will not be started.<br />By default, this value is 0.'), { datatype: 'port' } ],
	[ form.Value, 'admin_user', _('Admin user'), _('AdminUser specifies the username that the admin server will use for login.<br />By default, this value is "admin".') ],
	[ form.Value, 'admin_pwd', _('Admin password'), _('AdminPwd specifies the password that the admin server will use for login.<br />By default, this value is "admin".'), { password: true } ],
	[ form.Value, 'assets_dir', _('Assets dir'), _('AssetsDir specifies the local directory that the admin server will load resources from. If this value is "", assets will be loaded from the bundled executable using statik.<br />By default, this value is "".') ],
	[ form.Flag, 'tcp_mux', _('TCP mux'), _('TcpMux toggles TCP stream multiplexing. This allows multiple requests from a client to share a single TCP connection. If this value is true, the server must have TCP multiplexing enabled as well.<br />By default, this value is true.'), { datatype: 'bool', default: 'true' } ],
	[ form.Value, 'user', frpT('User'), _('User specifies a prefix for proxy names to distinguish them from other clients. If this value is not "", proxy names will automatically be changed to "{user}.{proxy_name}".<br />By default, this value is "".') ],
	[ form.Flag, 'login_fail_exit', _('Exit when login fail'), _('LoginFailExit controls whether or not the client should exit after a failed login attempt. If false, the client will retry until a login attempt succeeds.<br />By default, this value is true.'), { datatype: 'bool', default: 'true' } ],
	[ form.ListValue, 'protocol', frpT('Protocol'), _('Protocol specifies the protocol to use when interacting with the server. Valid values are "tcp", "kcp", "quic" and "websocket".<br />By default, this value is "tcp".'), { values: [ 'tcp', 'kcp', 'quic', 'websocket' ], placeholder: frpT('-- Please choose --') } ],
	[ form.Flag, 'tls_enable', _('TLS'), _('TLS Enable specifies whether or not TLS should be used when communicating with the server.'), { datatype: 'bool' } ],
	[ form.Value, 'heartbeat_interval', _('Heartbeat interval'), _('HeartBeatInterval specifies at what interval heartbeats are sent to the server, in seconds. It is not recommended to change this value.<br />By default, this value is 30.'), { datatype: 'uinteger' } ],
	[ form.Value, 'heartbeat_timeout', _('Heartbeat timeout'), _('HeartBeatTimeout specifies the maximum allowed heartbeat response delay before the connection is terminated, in seconds. It is not recommended to change this value.<br />By default, this value is 90.'), { datatype: 'uinteger' } ],
	[ form.DynamicList, '_', _('Additional settings'), _('This list can be used to specify INI parameters which have not been included in this LuCI.'), { placeholder: 'Key-A=Value-A' } ]
];

const baseProxyConf = [
	[ form.Value, 'name', _('Proxy name'), undefined, { rmempty: false, optional: false } ],
	[ form.ListValue, 'type', _('Proxy type'), _('ProxyType specifies the type of this proxy. Valid values include "tcp", "udp", "tcp_udp", "http", "https", "stcp" and "xtcp".<br />By default, this value is "tcp".'), { values: [ [ 'tcp', 'TCP' ], [ 'udp', 'UDP' ], [ 'tcp_udp', _('TCP + UDP') ], [ 'http', 'HTTP' ], [ 'https', 'HTTPS' ], [ 'stcp', 'STCP' ], [ 'xtcp', 'XTCP' ] ] } ],
	[ form.Flag, 'use_encryption', _('Encryption'), _('UseEncryption controls whether or not communication with the server will be encrypted. Encryption is done using the tokens supplied in the server and client configuration.<br />By default, this value is false.'), { datatype: 'bool' } ],
	[ form.Flag, 'use_compression', _('Compression'), _('UseCompression controls whether or not communication with the server will be compressed.<br />By default, this value is false.'), { datatype: 'bool' } ],
	[ form.Value, 'local_ip', _('Local IP'), _('LocalIp specifies the IP address or host name to proxy to.'), { datatype: 'host' } ],
	[ form.Value, 'local_port', _('Local port'), _('LocalPort specifies the port to proxy to.'), { datatype: 'port' } ]
];

const bindInfoConf = [
	[ form.Value, 'remote_port', _('Remote port'), _('If remote_port is 0, the server will assign a random port for this proxy.'), { datatype: 'port' } ]
];

const domainConf = [
	[ form.Value, 'custom_domains', _('Custom domains') ],
	[ form.Value, 'subdomain', _('Subdomain') ]
];

const httpProxyConf = [
	[ form.Value, 'locations', _('Locations') ],
	[ form.Value, 'http_user', _('HTTP user') ],
	[ form.Value, 'http_pwd', _('HTTP password') ],
	[ form.Value, 'host_header_rewrite', _('Host header rewrite') ]
];

const stcpProxyConf = [
	[ form.ListValue, 'role', _('Role'), undefined, { values: [ 'server', 'visitor' ] } ],
	[ form.Value, 'server_name', _('Server name'), undefined, { depends: [ { role: 'visitor' } ] } ],
	[ form.Value, 'bind_addr', _('Bind addr'), undefined, { depends: [ { role: 'visitor' } ] } ],
	[ form.Value, 'bind_port', _('Bind port'), undefined, { depends: [ { role: 'visitor' } ] } ],
	[ form.Value, 'sk', _('Sk') ]
];

const pluginConf = [
	[ form.ListValue, 'plugin', _('Plugin'), undefined, { values: [ '', 'http_proxy', 'socks5', 'unix_domain_socket' ], rmempty: true } ],
	[ form.Value, 'plugin_http_user', _('HTTP user'), undefined, { depends: { plugin: 'http_proxy' } } ],
	[ form.Value, 'plugin_http_passwd', _('HTTP password'), undefined, { depends: { plugin: 'http_proxy' } } ],
	[ form.Value, 'plugin_user', _('SOCKS5 user'), undefined, { depends: { plugin: 'socks5' } } ],
	[ form.Value, 'plugin_passwd', _('SOCKS5 password'), undefined, { depends: { plugin: 'socks5' } } ],
	[ form.Value, 'plugin_unix_path', _('Unix domain socket path'), undefined, { depends: { plugin: 'unix_domain_socket' }, optional: false, rmempty: false, datatype: 'file', placeholder: '/var/run/docker.sock', default: '/var/run/docker.sock' } ]
];

const pageStyle = [
	'.frp-service-status { display: inline-flex; gap: 2.5em; align-items: center; flex-wrap: wrap; }',
	'.frp-service-status-item { white-space: nowrap; }',
	'.cbi-tabmenu { display: flex; flex-wrap: nowrap; overflow-x: auto; white-space: nowrap; }',
	'.cbi-tabmenu > li { flex: 0 0 auto; }'
].join('\n');

let normalizeClientProxiesLock = null;

function stripProxyProtocolSuffix(name) {
	return String(name || '').replace(/_(tcp|udp|http|https|stcp|xtcp)$/i, '');
}

function makeProxyName(name, type) {
	const suffixMap = {
		tcp: 'tcp',
		udp: 'udp',
		http: 'http',
		https: 'https',
		stcp: 'stcp',
		xtcp: 'xtcp'
	};

	const suffix = suffixMap[type];
	let base = stripProxyProtocolSuffix(name);

	if (!base)
		base = 'proxy';

	return suffix ? '%s_%s'.format(base, suffix) : base;
}

function snapshotProxyOptions(section) {
	const data = {};

	for (let key in section) {
		if (key.charAt(0) === '.')
			continue;

		data[key] = section[key];
	}

	return data;
}

function findProxySection(name, type) {
	const sections = uci.sections('frpc', 'conf') || [];

	for (let section of sections) {
		const sid = section['.name'];

		if (sid === 'common')
			continue;

		if (section.name === name && section.type === type)
			return sid;
	}

	return null;
}

function writeProxyOptions(dstSection, src, type, name) {
	for (let key in src) {
		if (key === 'name' || key === 'type')
			continue;

		uci.set('frpc', dstSection, key, src[key]);
	}

	uci.set('frpc', dstSection, 'type', type);
	uci.set('frpc', dstSection, 'name', name);
}

function removeDuplicateProxySections() {
	const sections = uci.sections('frpc', 'conf') || [];
	const seen = {};

	for (let section of sections) {
		const sid = section['.name'];

		if (sid === 'common')
			continue;

		const type = section.type;

		if ([ 'tcp', 'udp', 'http', 'https', 'stcp', 'xtcp' ].indexOf(type) < 0)
			continue;

		const name = makeProxyName(section.name, type);
		const key = '%s:%s'.format(type, name);

		if (seen[key]) {
			uci.remove('frpc', sid);
			continue;
		}

		seen[key] = true;
		uci.set('frpc', sid, 'name', name);
	}
}

function normalizeClientProxiesOnce() {
	const sections = uci.sections('frpc', 'conf') || [];
	const tcpUdpList = [];

	for (let section of sections) {
		const sid = section['.name'];

		if (sid === 'common')
			continue;

		const type = section.type || 'tcp';

		if (type === 'tcp_udp') {
			tcpUdpList.push({
				sid: sid,
				data: snapshotProxyOptions(section)
			});
		}
		else if ([ 'tcp', 'udp', 'http', 'https', 'stcp', 'xtcp' ].indexOf(type) >= 0) {
			uci.set('frpc', sid, 'name', makeProxyName(section.name, type));
		}
	}

	for (let item of tcpUdpList) {
		const src = item.data;
		const tcpName = makeProxyName(src.name, 'tcp');
		const udpName = makeProxyName(src.name, 'udp');


		uci.remove('frpc', item.sid);

		let tcpSection = findProxySection(tcpName, 'tcp');
		if (!tcpSection)
			tcpSection = uci.add('frpc', 'conf');

		writeProxyOptions(tcpSection, src, 'tcp', tcpName);

		let udpSection = findProxySection(udpName, 'udp');
		if (!udpSection)
			udpSection = uci.add('frpc', 'conf');

		writeProxyOptions(udpSection, src, 'udp', udpName);
	}

	removeDuplicateProxySections();

	return uci.save();
}

function normalizeClientProxies() {
	if (normalizeClientProxiesLock)
		return normalizeClientProxiesLock;

	normalizeClientProxiesLock = uci.load('frpc').then(function() {
		return normalizeClientProxiesOnce();
	}).then(function(ret) {
		normalizeClientProxiesLock = null;
		return ret;
	}).catch(function(e) {
		normalizeClientProxiesLock = null;
		throw e;
	});

	return normalizeClientProxiesLock;
}

function setParams(o, params) {
	if (!params)
		return;

	for (let key in params) {
		let val = params[key];

		if (key === 'values') {
			for (let v of val) {
				let args = v;

				if (!Array.isArray(args))
					args = [ args ];

				o.value.apply(o, args);
			}
		}
		else if (key === 'depends') {
			if (!Array.isArray(val))
				val = [ val ];

			const oldDeps = o.deps && o.deps.length ? o.deps : [ {} ];
			const deps = [];

			for (let v of val) {
				const d = {};

				for (let vkey in v)
					d[vkey] = v[vkey];

				for (let od of oldDeps) {
					const merged = {};

					for (let dkey in od)
						merged[dkey] = od[dkey];

					for (let dkey in d)
						merged[dkey] = d[dkey];

					deps.push(merged);
				}
			}

			o.deps = deps;
		}
		else {
			o[key] = params[key];
		}
	}

	if (params.datatype === 'bool') {
		o.enabled = 'true';
		o.disabled = 'false';
	}
}

function defTabOpts(s, t, opts, params) {
	for (let opt of opts) {
		const o = s.taboption(t, opt[0], opt[1], opt[2], opt[3]);

		setParams(o, opt[4]);
		setParams(o, params);
	}
}

function defOpts(s, opts, params) {
	for (let opt of opts) {
		const o = s.option(opt[0], opt[1], opt[2], opt[3]);

		setParams(o, opt[4]);
		setParams(o, params);
	}
}

const callServiceList = rpc.declare({
	object: 'service',
	method: 'list',
	params: [ 'name' ],
	expect: { '': {} }
});

const callRcInit = rpc.declare({
	object: 'rc',
	method: 'init',
	params: [ 'name', 'action' ]
});

function getServiceStatus(name) {
	return L.resolveDefault(callServiceList(name), {}).then(function(res) {
		try {
			const instances = res[name].instances;

			for (let key in instances)
				if (instances[key].running)
					return true;
		}
		catch (e) {}

		return false;
	});
}

function getAllServiceStatus() {
	return getServiceStatus('frpc').then(function(running) {
		return {
			frpc: running
		};
	});
}

function renderOneStatus(label) {
	return '<em class="frp-service-status-item"><span style="color:green"><strong>%s %s</strong></span></em>'.format(label, frpT('Running'));
}

function renderStatus(status) {
	const items = [];

	if (status.frpc)
		items.push(renderOneStatus(_('frp Client')));

	return items.length ? '<span class="frp-service-status">%s</span>'.format(items.join('')) : '';
}

function updateServiceStatus() {
	return L.resolveDefault(getAllServiceStatus()).then(function(res) {
		const statusView = document.getElementById('service_status');

		if (statusView)
			statusView.innerHTML = renderStatus(res);
	});
}

function serviceActionTitle(action) {
	return action === 'start' ? _('Start service') : _('Stop service');
}

function handleServiceAction(name, action) {
	return callRcInit(name, action).then(function(ret) {
		if (ret)
			throw _('Command failed');

		window.setTimeout(updateServiceStatus, 1000);
	}).catch(function(e) {
		ui.addNotification(null, E('p', _('Failed to execute "/etc/init.d/%s %s" action: %s').format(name, action, e)));
	});
}

function defServiceActionButtons(s, tab, name, params) {
	for (let action of [ 'start', 'stop' ]) {
		const title = serviceActionTitle(action);
		const o = s.taboption(tab, form.Button, '_%s_%s'.format(name, action), title);

		o.inputtitle = title;
		o.inputstyle = action === 'start' ? 'positive' : 'negative';
		o.onclick = function() {
			return handleServiceAction(name, action);
		};

		setParams(o, params);
	}
}

return view.extend({
	render: function() {
		let m, s, o;

		m = new form.Map('frpc', _('frp Client'));

		s = m.section(form.NamedSection, '_status');
		s.anonymous = true;
		s.render = function(section_id) {
			L.Poll.add(function() {
				return L.resolveDefault(getAllServiceStatus()).then(function(res) {
					const statusView = document.getElementById('service_status');

					if (statusView)
						statusView.innerHTML = renderStatus(res);
				});
			});

			return E('div', { class: 'cbi-map' }, [
				E('style', {}, pageStyle),
				E('fieldset', { class: 'cbi-section' }, [
					E('p', { id: 'service_status' }, _('Collecting data ...'))
				])
			]);
		};

		s = m.section(form.NamedSection, 'common', 'conf');
		s.dynamic = true;
		s.tab('client_common', _('Client Common Settings'));
		s.tab('client_init', _('Client Startup Settings'));
		defServiceActionButtons(s, 'client_common', 'frpc');
		defTabOpts(s, 'client_common', clientCommonConf, { optional: true });

		o = s.taboption('client_common', form.SectionValue, 'client_proxy', form.GridSection, 'conf', _('Client Proxy Settings'));
		let clientProxySection = o.subsection;
		clientProxySection.anonymous = true;
		clientProxySection.addremove = true;
		clientProxySection.sortable = true;
		clientProxySection.addbtntitle = _('Add new proxy...');
		clientProxySection.filter = function(section_id) {
			return section_id !== 'common';
		};
		clientProxySection.tab('general', _('General Settings'));
		clientProxySection.tab('http', _('HTTP Settings'));
		clientProxySection.tab('plugin', _('Plugin Settings'));
		clientProxySection.option(form.Value, 'name', _('Proxy name')).modalonly = false;
		o = clientProxySection.option(form.ListValue, 'type', _('Proxy type'));
		o.value('tcp', 'TCP');
		o.value('udp', 'UDP');
		o.value('tcp_udp', _('TCP + UDP'));
		o.value('http', 'HTTP');
		o.value('https', 'HTTPS');
		o.value('stcp', 'STCP');
		o.value('xtcp', 'XTCP');
		o.modalonly = false;
		clientProxySection.option(form.Value, 'local_ip', _('Local IP')).modalonly = false;
		clientProxySection.option(form.Value, 'local_port', _('Local port')).modalonly = false;
		o = clientProxySection.option(form.Value, 'remote_port', _('Remote port'));
		o.modalonly = false;
		o.depends('type', 'tcp');
		o.depends('type', 'udp');
		o.depends('type', 'tcp_udp');
		o.cfgvalue = function() {
			const v = this.super('cfgvalue', arguments);

			return v && v != '0' ? v : '#';
		};
		defTabOpts(clientProxySection, 'general', baseProxyConf, { modalonly: true });
		defTabOpts(clientProxySection, 'general', bindInfoConf, { optional: true, modalonly: true, depends: [ { type: 'tcp' }, { type: 'udp' }, { type: 'tcp_udp' } ] });
		defTabOpts(clientProxySection, 'http', domainConf, { optional: true, modalonly: true, depends: [ { type: 'http' }, { type: 'https' } ] });
		defTabOpts(clientProxySection, 'http', httpProxyConf, { optional: true, modalonly: true, depends: { type: 'http' } });
		defTabOpts(clientProxySection, 'general', stcpProxyConf, { modalonly: true, depends: [ { type: 'stcp' }, { type: 'xtcp' } ] });
		defTabOpts(clientProxySection, 'plugin', pluginConf, { modalonly: true });

		o = s.taboption('client_init', form.SectionValue, 'client_init', form.TypedSection, 'init', _('Client Startup Settings'));
		let clientInitSection = o.subsection;
		clientInitSection.anonymous = true;
		clientInitSection.dynamic = true;
		defOpts(clientInitSection, startupConf('frpc'));

		const originalSave = m.save.bind(m);

		m.save = function() {
			return originalSave.apply(this, arguments).then(function() {
				return normalizeClientProxies();
			});
		};

		return m.render();
	}
});
