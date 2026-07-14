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

function statusValue(id) {
	return E('span', { 'id': id }, _('Loading...'));
}

function updateStatus() {
	return callHardwareStatus().then(function(status) {
		var temperature = document.getElementById('ax900-hardware-temperature');
		var hottest = document.getElementById('ax900-hardware-hottest');
		var pwm = document.getElementById('ax900-hardware-pwm');
		var rpm = document.getElementById('ax900-hardware-rpm');

		if (temperature)
			temperature.textContent = status.temperature > 0 ? (status.temperature / 1000).toFixed(1) + ' C' : _('Unavailable');
		if (hottest)
			hottest.textContent = status.hottest || _('Unavailable');
		if (pwm)
			pwm.textContent = status.pwm >= 0 ? Math.round(status.pwm * 100 / 255) + '%' : _('Unavailable');
		if (rpm)
			rpm.textContent = status.rpm > 0 ? status.rpm + ' RPM' : _('No feedback');
	});
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

function addFrontColorValues(option) {
	option.value('blue', _('Blue'));
	option.value('yellow', _('Yellow'));
}

function addBlinkFields(section, prefix, modeOption, onLabel, offLabel) {
	var option = section.option(form.Value, prefix + '_on', onLabel + ' (ms)');
	option.datatype = 'range(100,60000)';
	option.default = '500';
	option.depends(modeOption, 'blink');

	option = section.option(form.Value, prefix + '_off', offLabel + ' (ms)');
	option.datatype = 'range(100,60000)';
	option.default = '500';
	option.depends(modeOption, 'blink');
}

function applyCardLayout(node) {
	var sections = Array.prototype.slice.call(node.querySelectorAll('.cbi-section'));
	if (sections.length !== 4)
		return;

	var parent = sections[0].parentNode;
	var layout = E('div', { 'class': 'ax900-hardware-layout' });
	var left = E('div', { 'class': 'ax900-hardware-column' });
	var right = E('div', { 'class': 'ax900-hardware-column' });

	parent.insertBefore(layout, sections[0]);
	layout.appendChild(left);
	layout.appendChild(right);
	left.appendChild(sections[0]);
	left.appendChild(sections[2]);
	right.appendChild(sections[1]);
	right.appendChild(sections[3]);
}

function inlineTemperatureBlinkOptions(node) {
	[
		['top_low_color', 'top_low_blink'],
		['top_mid_color', 'top_mid_blink'],
		['top_high_color', 'top_high_blink']
	].forEach(function(names) {
		var colorRow = node.querySelector('.cbi-value[data-name="' + names[0] + '"]');
		var blinkRow = node.querySelector('.cbi-value[data-name="' + names[1] + '"]');
		var colorField = colorRow ? colorRow.querySelector('.cbi-value-field') : null;

		if (!colorField || !blinkRow)
			return;

		colorRow.classList.add('ax900-temperature-color');
		blinkRow.classList.add('ax900-temperature-blink');
		colorField.appendChild(blinkRow);
	});
}

var layoutStyle = `
.ax900-hardware-layout {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 14px;
	align-items: start;
}
.ax900-hardware-column {
	display: flex;
	min-width: 0;
	flex-direction: column;
	gap: 14px;
}
.ax900-hardware-column > .cbi-section {
	min-width: 0;
	margin: 0;
}
.ax900-temperature-color > .cbi-value-field {
	display: flex;
	align-items: center;
	gap: 14px;
}
.ax900-temperature-color > .cbi-value-field > :first-child {
	min-width: 0;
	flex: 1 1 auto;
}
.ax900-temperature-blink {
	display: flex !important;
	width: auto !important;
	min-width: max-content;
	margin: 0 !important;
	padding: 0 !important;
	align-items: center;
	gap: 7px;
}
.ax900-temperature-blink > .cbi-value-title,
.ax900-temperature-blink > .cbi-value-field {
	width: auto !important;
	margin: 0 !important;
	padding: 0 !important;
}
.ax900-temperature-blink > .cbi-value-title {
	order: 2;
}
@media (max-width: 1100px) {
	.ax900-hardware-layout {
		grid-template-columns: minmax(0, 1fr);
	}
}
`;

return view.extend({
	load: function() {
		return uci.load('ax900-hardware');
	},

	render: function() {
		var map = new form.Map('ax900-hardware', _('Fan & LED'));
		var section = map.section(form.NamedSection, 'main', 'hardware', _('Current status'));
		section.anonymous = true;

		var option = section.option(form.DummyValue, '_temperature', _('Maximum temperature'));
		option.renderWidget = function() { return statusValue('ax900-hardware-temperature'); };
		option = section.option(form.DummyValue, '_hottest', _('Hottest sensor'));
		option.renderWidget = function() { return statusValue('ax900-hardware-hottest'); };
		option = section.option(form.DummyValue, '_pwm', _('Fan power'));
		option.renderWidget = function() { return statusValue('ax900-hardware-pwm'); };
		option = section.option(form.DummyValue, '_rpm', _('Speed feedback'));
		option.renderWidget = function() { return statusValue('ax900-hardware-rpm'); };

		section = map.section(form.NamedSection, 'main', 'hardware', _('Fan control'));
		section.anonymous = true;
		option = section.option(form.Flag, 'fan_enabled', _('Enable fan control'));
		option.rmempty = false;

		option = section.option(form.ListValue, 'fan_mode', _('Control mode'));
		option.value('auto', _('Automatic'));
		option.value('manual', _('Manual fixed power'));
		option.default = 'auto';
		option.depends('fan_enabled', '1');

		option = section.option(form.Value, 'manual_percent', _('Manual fan power') + ' (%)');
		option.datatype = 'range(0,100)';
		option.default = '50';
		option.depends({ fan_enabled: '1', fan_mode: 'manual' });

		[
			['low_temp', _('Low temperature'), '40'],
			['mid_temp', _('Medium temperature'), '50'],
			['high_temp', _('High temperature'), '65']
		].forEach(function(item) {
			option = section.option(form.Value, item[0], item[1] + ' (C)');
			option.datatype = 'range(20,100)';
			option.default = item[2];
			option.depends({ fan_enabled: '1', fan_mode: 'auto' });
		});

		[
			['low_percent', _('Low temperature fan power'), '0'],
			['mid_percent', _('Medium temperature fan power'), '50'],
			['high_percent', _('High temperature fan power'), '100']
		].forEach(function(item) {
			option = section.option(form.Value, item[0], item[1] + ' (%)');
			option.datatype = 'range(0,100)';
			option.default = item[2];
			option.depends({ fan_enabled: '1', fan_mode: 'auto' });
		});

		option = section.option(form.Value, 'interval', _('Temperature polling interval') + ' (s)');
		option.datatype = 'range(2,60)';
		option.default = '5';
		option.depends('fan_enabled', '1');

		section = map.section(form.NamedSection, 'main', 'hardware', _('Top RGB LED'));
		section.anonymous = true;
		option = section.option(form.ListValue, 'top_mode', _('Lighting mode'));
		option.value('off', _('Off'));
		option.value('fixed', _('Fixed color'));
		option.value('temperature', _('Follow temperature'));
		option.value('cycle', _('Color cycle'));
		option.default = 'temperature';

		option = section.option(form.ListValue, 'top_fixed_color', _('Color'));
		addColorValues(option, false);
		option.default = 'blue';
		option.depends('top_mode', 'fixed');

		option = section.option(form.ListValue, 'top_low_color', _('Below medium temperature'));
		addColorValues(option, true);
		option.default = 'blue';
		option.depends('top_mode', 'temperature');
		option = section.option(form.Flag, 'top_low_blink', _('Blink'));
		option.default = '0';
		option.depends('top_mode', 'temperature');
		option = section.option(form.ListValue, 'top_mid_color', _('At medium temperature'));
		addColorValues(option, true);
		option.default = 'yellow';
		option.depends('top_mode', 'temperature');
		option = section.option(form.Flag, 'top_mid_blink', _('Blink'));
		option.default = '0';
		option.depends('top_mode', 'temperature');
		option = section.option(form.ListValue, 'top_high_color', _('At high temperature'));
		addColorValues(option, true);
		option.default = 'red';
		option.depends('top_mode', 'temperature');
		option = section.option(form.Flag, 'top_high_blink', _('Blink'));
		option.default = '0';
		option.depends('top_mode', 'temperature');

		option = section.option(form.Flag, 'top_blink', _('Blink'));
		option.default = '0';
		option.depends('top_mode', 'fixed');

		option = section.option(form.Value, 'top_blink_on', _('On time') + ' (ms)');
		option.datatype = 'range(100,60000)';
		option.default = '500';
		option.depends({ top_mode: 'fixed', top_blink: '1' });
		option.depends({ top_mode: 'temperature', top_low_blink: '1' });
		option.depends({ top_mode: 'temperature', top_mid_blink: '1' });
		option.depends({ top_mode: 'temperature', top_high_blink: '1' });
		option = section.option(form.Value, 'top_blink_off', _('Off time') + ' (ms)');
		option.datatype = 'range(100,60000)';
		option.default = '500';
		option.depends({ top_mode: 'fixed', top_blink: '1' });
		option.depends({ top_mode: 'temperature', top_low_blink: '1' });
		option.depends({ top_mode: 'temperature', top_mid_blink: '1' });
		option.depends({ top_mode: 'temperature', top_high_blink: '1' });

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
		addFrontColorValues(option);
		option.default = 'blue';
		option.depends('system_led_mode', 'fixed');
		option.depends('system_led_mode', 'blink');
		addBlinkFields(section, 'system_led', 'system_led_mode', _('System LED on time'), _('System LED off time'));

		option = section.option(form.ListValue, 'network_led_mode', _('Network LED'));
		option.value('netdev', _('Follow WAN activity'));
		option.value('off', _('Off'));
		option.value('fixed', _('Fixed color'));
		option.value('blink', _('Blink'));
		option.default = 'netdev';
		option = section.option(form.ListValue, 'network_led_color', _('Network LED color'));
		addFrontColorValues(option);
		option.default = 'yellow';
		option.depends('network_led_mode', 'netdev');
		option.depends('network_led_mode', 'fixed');
		option.depends('network_led_mode', 'blink');
		addBlinkFields(section, 'network_led', 'network_led_mode', _('Network LED on time'), _('Network LED off time'));

		return map.render().then(function(node) {
			inlineTemperatureBlinkOptions(node);
			applyCardLayout(node);
			poll.add(updateStatus);
			window.setTimeout(updateStatus, 0);
			return E([], [ E('style', {}, layoutStyle), node ]);
		});
	}
});
