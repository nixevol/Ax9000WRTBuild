'use strict';
'require form';
'require poll';
'require rpc';
'require uci';
'require view';

var callHardwareStatus = rpc.declare({
	object: 'ax900-hardware',
	method: 'status',
	expect: {}
});

function updateStatus() {
	return callHardwareStatus().then(function(status) {
		var temperature = document.getElementById('ax900-hardware-temperature');
		var pwm = document.getElementById('ax900-hardware-pwm');
		var rpm = document.getElementById('ax900-hardware-rpm');

		if (temperature)
			temperature.textContent = status.temperature > 0 ? (status.temperature / 1000).toFixed(1) + ' C' : _('Unavailable');
		if (pwm)
			pwm.textContent = status.pwm >= 0 ? Math.round(status.pwm * 100 / 255) + '%' : _('Unavailable');
		if (rpm)
			rpm.textContent = status.rpm > 0 ? status.rpm + ' RPM' : _('No feedback');
	});
}

function statusItem(icon, id, label) {
	var iconUrl = L.resource('ax900-hardware/icons/' + icon + '.svg');
	return E('div', {
		'class': 'ax900-status-item',
		'title': label,
		'aria-label': label
	}, [
		E('span', {
			'class': 'ax900-status-icon',
			'style': 'mask-image:url(' + iconUrl + ');-webkit-mask-image:url(' + iconUrl + ')',
			'aria-hidden': 'true'
		}),
		E('span', { 'id': id }, _('Loading...'))
	]);
}

function addColorValues(option, includeOff) {
	option.value('red', _('Red'));
	option.value('green', _('Green'));
	option.value('blue', _('Blue'));
	option.value('yellow', _('Yellow'));
	option.value('purple', _('Purple'));
	option.value('cyan', _('Cyan'));
	option.value('white', _('White'));
	if (includeOff)
		option.value('off', _('Off'));
}

function addFrontColorValues(option, includeOff) {
	option.value('blue', _('Blue'));
	option.value('yellow', _('Yellow'));
	if (includeOff)
		option.value('off', _('Off'));
}

function colorTextValue(sectionId) {
	var value = this.cfgvalue(sectionId) || this.default || 'off';
	var labels = {
		red: _('Red'),
		green: _('Green'),
		blue: _('Blue'),
		yellow: _('Yellow'),
		purple: _('Purple'),
		cyan: _('Cyan'),
		white: _('White'),
		off: _('Off')
	};
	return E('span', { 'class': 'ax900-color-value' }, [
		E('span', { 'class': 'ax900-color-swatch ax900-color-' + value }),
		labels[value] || value
	]);
}

function addBlinkFields(section, prefix, modeOption, onLabel, offLabel, extraDepends) {
	var option = section.option(form.Value, prefix + '_on', onLabel + ' (ms)');
	option.datatype = 'range(100,60000)';
	option.default = '500';
	option.depends(modeOption, 'blink');
	(extraDepends || []).forEach(function(dependency) { option.depends(dependency); });

	option = section.option(form.Value, prefix + '_off', offLabel + ' (ms)');
	option.datatype = 'range(100,60000)';
	option.default = '500';
	option.depends(modeOption, 'blink');
	(extraDepends || []).forEach(function(dependency) { option.depends(dependency); });
}

function validateTime(sectionId, value) {
	return /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(value)
		? true
		: _('Use 24-hour time in HH:MM format');
}

function systemPollInterval() {
	var value = String(L.env.pollinterval || '');
	var interval = Number(value);

	return /^\d+$/.test(value) && interval >= 1 && interval <= 60 ? interval : 5;
}

function pageAction(label, className, selector) {
	return E('button', {
		'type': 'button',
		'class': 'cbi-button ' + className,
		'data-action-selector': selector,
		'disabled': true,
		'click': function(event) {
			var target = document.querySelector('#view .cbi-page-actions ' + selector);

			event.preventDefault();
			if (target && !target.disabled)
				target.click();
		}
	}, [ label ]);
}

function syncPageActions(node) {
	var buttons = node.querySelectorAll('.ax900-actions [data-action-selector]');

	Array.prototype.forEach.call(buttons, function(button) {
		var selector = button.getAttribute('data-action-selector');
		var target = document.querySelector('#view .cbi-page-actions ' + selector);

		button.disabled = !target || target.disabled;
	});
}

function decorateTitle(node) {
	var title = node.querySelector('.cbi-map > h2');
	if (!title)
		return;

	var bar = E('div', { 'class': 'ax900-titlebar' }, [
		E('h2', {}, title.textContent)
	]);
	var status = E('div', { 'class': 'ax900-statusbar' }, [
		E('div', { 'class': 'ax900-status', 'aria-label': _('Current status') }, [
			statusItem('temperature', 'ax900-hardware-temperature', _('Maximum temperature')),
			statusItem('fan', 'ax900-hardware-pwm', _('Fan power')),
			statusItem('gauge', 'ax900-hardware-rpm', _('Speed feedback'))
		]),
		E('div', { 'class': 'ax900-actions' }, [
			pageAction(_('Save & Apply'), 'cbi-button-apply important', '.cbi-button-apply'),
			pageAction(_('Save'), 'cbi-button-save', '.cbi-button-save'),
			pageAction(_('Reset'), 'cbi-button-reset', '.cbi-button-reset')
		])
	]);
	title.parentNode.replaceChild(bar, title);
	bar.parentNode.insertBefore(status, bar.nextSibling);
}

function applyWorkspace(node) {
	var sections = Array.prototype.slice.call(node.querySelectorAll('.cbi-section'));
	if (sections.length !== 5)
		return;

	var schedule = sections[0];
	var fan = sections[1];
	var rules = sections[2];
	var top = sections[3];
	var front = sections[4];
	var parent = schedule.parentNode;
	var workspace = E('div', { 'class': 'ax900-workspace' });

	rules.classList.add('ax900-rules');
	top.classList.add('ax900-top-led');
	parent.insertBefore(workspace, schedule);
	workspace.appendChild(schedule);
	workspace.appendChild(front);
	workspace.appendChild(fan);
	workspace.appendChild(top);
	workspace.appendChild(rules);
}

function syncConditionalSections(node, fanEnabledOption, fanModeOption) {
	var rules = node.querySelector('.ax900-rules');
	var top = node.querySelector('.ax900-top-led');
	var enabled = fanEnabledOption.formvalue('main') === '1';
	var automatic = enabled && fanModeOption.formvalue('main') === 'auto';
	var ledInputs = node.querySelectorAll('.ax900-rules [data-name="led_control"] input[type="checkbox"]');
	var temperatureControlsLed = Array.prototype.some.call(ledInputs, function(input) {
		return input.checked;
	});

	if (!ledInputs.length) {
		temperatureControlsLed = uci.sections('ax900-hardware', 'fan_rule').some(function(rule) {
			return rule.led_control === '1';
		});
	}
	if (rules)
		rules.classList.toggle('ax900-hidden', !automatic);
	if (top)
		top.classList.toggle('ax900-hidden', automatic && temperatureControlsLed);
}

var layoutStyle = `
.ax900-titlebar {
	width: 100%;
	min-height: 42px;
	margin: 0 0 12px;
}
.ax900-titlebar h2 {
	margin: 0;
}
.ax900-statusbar {
	display: flex;
	width: 100%;
	margin: 14px 0 10px;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
}
.ax900-status {
	display: grid;
	grid-template-columns: repeat(3, minmax(108px, auto));
	gap: 8px;
}
.ax900-status-item {
	display: flex;
	min-height: 30px;
	padding: 0 9px;
	align-items: center;
	justify-content: center;
	gap: 8px;
	border: 1px solid var(--border-color-medium, #d8dde5);
	border-radius: 6px;
	background: var(--background-color-high, rgba(127, 127, 127, .06));
	font-variant-numeric: tabular-nums;
	white-space: nowrap;
}
.ax900-status-icon {
	display: inline-block;
	width: 18px;
	height: 18px;
	background: currentColor;
	mask-position: center;
	mask-repeat: no-repeat;
	mask-size: contain;
	-webkit-mask-position: center;
	-webkit-mask-repeat: no-repeat;
	-webkit-mask-size: contain;
	opacity: .68;
}
.ax900-actions {
	display: flex;
	margin-left: auto;
	align-items: center;
	justify-content: flex-end;
	gap: 8px;
	white-space: nowrap;
}
.ax900-actions .cbi-button {
	min-width: 76px;
	margin: 0;
}
.ax900-actions .cbi-button-apply {
	min-width: 104px;
}
.ax900-workspace {
	display: flex;
	width: 100%;
	flex-direction: column;
	margin: 0;
	gap: 12px;
}
.ax900-workspace > .cbi-section {
	margin: 0 !important;
}
.ax900-rules .table {
	min-width: 100%;
}
.ax900-rules .cbi-section-node {
	overflow-x: auto;
}
.ax900-rules .table .tr {
	min-width: 700px;
}
.ax900-color-value {
	display: inline-flex;
	align-items: center;
	gap: 7px;
}
.ax900-color-swatch {
	display: inline-block;
	width: 10px;
	height: 10px;
	border: 1px solid rgba(0, 0, 0, .18);
	border-radius: 50%;
}
.ax900-color-red { background: #dc2626; }
.ax900-color-green { background: #16a34a; }
.ax900-color-blue { background: #2563eb; }
.ax900-color-yellow { background: #eab308; }
.ax900-color-purple { background: #9333ea; }
.ax900-color-cyan { background: #06b6d4; }
.ax900-color-white { background: #fff; }
.ax900-color-off { background: transparent; }
.ax900-hidden {
	display: none !important;
}
.ax900-workspace .hidden {
	display: none !important;
}
@media (max-width: 820px) {
	.ax900-statusbar {
		flex-wrap: wrap;
	}
	.ax900-status {
		width: 100%;
		grid-template-columns: repeat(3, minmax(100px, 1fr));
	}
	.ax900-actions {
		width: 100%;
	}
}
`;

return view.extend({
	load: function() {
		return uci.load('ax900-hardware');
	},

	render: function() {
		var map = new form.Map('ax900-hardware', _('Fan & LED'));
		var fanEnabledOption;
		var fanModeOption;
		var section = map.section(form.NamedSection, 'main', 'hardware', _('Scheduled lighting'));
		section.anonymous = true;
		var option = section.option(form.Flag, 'schedule_enabled', _('Enable schedule'));
		option.default = '0';
		option.rmempty = false;
		option = section.option(form.Value, 'schedule_start', _('Start time'));
		option.default = '23:00';
		option.validate = validateTime;
		option.depends('schedule_enabled', '1');
		option = section.option(form.Value, 'schedule_end', _('End time'));
		option.default = '07:00';
		option.validate = validateTime;
		option.depends('schedule_enabled', '1');
		option = section.option(form.ListValue, 'schedule_action', _('Scheduled action'));
		option.value('off', _('Force off'));
		option.value('on', _('Force on'));
		option.default = 'off';
		option.depends('schedule_enabled', '1');
		option = section.option(form.Flag, 'schedule_top', _('Top RGB LED'));
		option.default = '1';
		option.depends('schedule_enabled', '1');
		option = section.option(form.Flag, 'schedule_system', _('System LED'));
		option.default = '1';
		option.depends('schedule_enabled', '1');
		option = section.option(form.Flag, 'schedule_network', _('Network LED'));
		option.default = '1';
		option.depends('schedule_enabled', '1');

		section = map.section(form.NamedSection, 'main', 'hardware', _('Fan control'));
		section.anonymous = true;
		option = section.option(form.Flag, 'fan_enabled', _('Enable fan control'));
		option.rmempty = false;
		fanEnabledOption = option;
		option = section.option(form.ListValue, 'fan_mode', _('Control mode'));
		option.value('auto', _('Automatic'));
		option.value('manual', _('Manual fixed power'));
		option.default = 'auto';
		option.rmempty = false;
		option.depends('fan_enabled', '1');
		fanModeOption = option;
		option = section.option(form.Value, 'interval', _('Detection interval') + ' (s)');
		option.datatype = 'range(1,60)';
		option.placeholder = _('System default (%s s)').format(systemPollInterval());
		option.rmempty = true;
		option.depends('fan_enabled', '1');
		option = section.option(form.Value, 'manual_percent', _('Manual fan power') + ' (%)');
		option.datatype = 'range(0,100)';
		option.default = '50';
		option.depends({ fan_enabled: '1', fan_mode: 'manual' });

		section = map.section(form.GridSection, 'fan_rule', _('Automatic temperature rules'),
			_('Rules are checked from top to bottom; evaluation stops at the first match.'));
		section.anonymous = true;
		section.addremove = true;
		section.sortable = true;
		section.addbtntitle = _('Add rule');
		option = section.option(form.ListValue, 'operator', _('Condition'));
		option.value('ge', '≥');
		option.value('le', '≤');
		option.default = 'ge';
		option.textvalue = function(sectionId) {
			return (this.cfgvalue(sectionId) || this.default) === 'le' ? '≤' : '≥';
		};
		option = section.option(form.Value, 'threshold', _('Temperature') + ' (C)');
		option.datatype = 'range(0,120)';
		option.default = '50';
		option = section.option(form.Value, 'power', _('Fan power') + ' (%)');
		option.datatype = 'range(0,100)';
		option.default = '50';
		option = section.option(form.Flag, 'led_control', _('Control top RGB'));
		option.default = '0';
		option = section.option(form.ListValue, 'led_color', _('LED color'));
		addColorValues(option, true);
		option.default = 'blue';
		option.depends('led_control', '1');
		option.textvalue = colorTextValue;

		section = map.section(form.NamedSection, 'main', 'hardware', _('Top RGB LED'));
		section.anonymous = true;
		option = section.option(form.ListValue, 'top_mode', _('Lighting mode'));
		option.value('off', _('Off'));
		option.value('fixed', _('Fixed color'));
		option.value('cycle', _('Color cycle'));
		option.default = 'fixed';
		option = section.option(form.ListValue, 'top_fixed_color', _('Color'));
		addColorValues(option, false);
		option.default = 'blue';
		option.depends('top_mode', 'fixed');
		option = section.option(form.Flag, 'top_blink', _('Blink'));
		option.default = '0';
		option.depends('top_mode', 'fixed');
		option = section.option(form.Value, 'top_blink_on', _('On time') + ' (ms)');
		option.datatype = 'range(100,60000)';
		option.default = '500';
		option.depends({ top_mode: 'fixed', top_blink: '1' });
		option = section.option(form.Value, 'top_blink_off', _('Off time') + ' (ms)');
		option.datatype = 'range(100,60000)';
		option.default = '500';
		option.depends({ top_mode: 'fixed', top_blink: '1' });
		option = section.option(form.Value, 'top_cycle_interval', _('Color cycle interval') + ' (s)');
		option.datatype = 'range(1,60)';
		option.default = '3';
		option.depends('top_mode', 'cycle');

		section = map.section(form.NamedSection, 'main', 'hardware', _('Front LEDs'));
		section.anonymous = true;
		option = section.option(form.ListValue, 'system_led_mode', _('System LED'));
		option.value('default', _('System default'));
		option.value('off', _('Off'));
		option.value('fixed', _('Fixed color'));
		option.value('blink', _('Blink'));
		option.default = 'default';
		option = section.option(form.ListValue, 'system_led_color', _('System LED color'));
		addFrontColorValues(option, false);
		option.default = 'blue';
		option.depends('system_led_mode', 'fixed');
		option.depends('system_led_mode', 'blink');
		addBlinkFields(section, 'system_led', 'system_led_mode', _('System LED on time'), _('System LED off time'));

		option = section.option(form.ListValue, 'network_led_mode', _('Network LED'));
		option.value('netdev', _('Follow WAN activity'));
		option.value('connectivity', _('Follow network connectivity'));
		option.value('off', _('Off'));
		option.value('fixed', _('Fixed color'));
		option.value('blink', _('Blink'));
		option.default = 'connectivity';
		option = section.option(form.ListValue, 'network_led_color', _('Network LED color'));
		addFrontColorValues(option, false);
		option.default = 'yellow';
		option.depends('network_led_mode', 'netdev');
		option.depends('network_led_mode', 'fixed');
		option.depends('network_led_mode', 'blink');
		addBlinkFields(section, 'network_led', 'network_led_mode', _('Network LED on time'), _('Network LED off time'), [
			{ network_led_mode: 'connectivity', network_online_color: 'blue', network_online_blink: '1' },
			{ network_led_mode: 'connectivity', network_online_color: 'yellow', network_online_blink: '1' },
			{ network_led_mode: 'connectivity', network_offline_color: 'blue', network_offline_blink: '1' },
			{ network_led_mode: 'connectivity', network_offline_color: 'yellow', network_offline_blink: '1' }
		]);
		option = section.option(form.Value, 'network_check_target', _('Ping target'));
		option.default = '223.5.5.5';
		option.datatype = 'host';
		option.depends('network_led_mode', 'connectivity');
		option = section.option(form.ListValue, 'network_online_color', _('Reachable color'));
		addFrontColorValues(option, true);
		option.default = 'blue';
		option.depends('network_led_mode', 'connectivity');
		option = section.option(form.Flag, 'network_online_blink', _('Blink when reachable'));
		option.default = '0';
		option.depends({ network_led_mode: 'connectivity', network_online_color: 'blue' });
		option.depends({ network_led_mode: 'connectivity', network_online_color: 'yellow' });
		option = section.option(form.ListValue, 'network_offline_color', _('Unreachable color'));
		addFrontColorValues(option, true);
		option.default = 'yellow';
		option.depends('network_led_mode', 'connectivity');
		option = section.option(form.Flag, 'network_offline_blink', _('Blink when unreachable'));
		option.default = '0';
		option.depends({ network_led_mode: 'connectivity', network_offline_color: 'blue' });
		option.depends({ network_led_mode: 'connectivity', network_offline_color: 'yellow' });

		var renderContents = map.renderContents;
		map.renderContents = function() {
			return renderContents.apply(this, arguments).then(function(node) {
				decorateTitle(node);
				applyWorkspace(node);
				map.checkDepends();
				syncConditionalSections(node, fanEnabledOption, fanModeOption);
				window.setTimeout(function() {
					syncPageActions(node);
					updateStatus();
				}, 0);
				return node;
			});
		};

		return map.render().then(function(node) {
			var refreshDependencies = function() {
				window.setTimeout(function() {
					map.checkDepends();
					syncConditionalSections(node, fanEnabledOption, fanModeOption);
				}, 0);
			};
			node.addEventListener('change', refreshDependencies);
			node.addEventListener('cbi-dropdown-change', refreshDependencies);
			new MutationObserver(function() {
				syncConditionalSections(node, fanEnabledOption, fanModeOption);
			}).observe(node, { childList: true, subtree: true });
			poll.add(updateStatus);
			return E([], [ E('style', {}, layoutStyle), node ]);
		});
	}
});
