<template>
  <n-config-provider>
    <n-message-provider>
      <div class="app-shell">
        <header class="topbar">
          <div class="brand-block">
            <div class="logo"><span>OPEN</span><strong>WRT</strong></div>
            <div class="product-copy">
              <div class="product-name">AX9000 固件构建器</div>
              <div class="product-version">OpenWrt 25.12 NSS</div>
            </div>
          </div>

          <div class="build-toolbar">
            <label class="remember-control">
              <span>记住配置</span>
              <n-switch v-model:value="rememberOptions" size="small" />
            </label>
            <div class="jobs-control">
              <span>线程</span>
              <n-input-number v-model:value="jobs" :min="0" :max="64" size="small" placeholder="自动" />
            </div>
            <n-checkbox v-model:checked="clean">全量清理</n-checkbox>
            <n-tag :type="statusTagType" size="small">{{ statusText }}</n-tag>
            <n-button type="primary" :disabled="status.running" @click="startBuild">
              <template #icon><n-icon><Settings /></n-icon></template>
              构建固件
            </n-button>
            <n-button v-if="status.running" type="error" :loading="status.stopping" @click="stopBuild">
              <template #icon><n-icon><Square /></n-icon></template>
              停止
            </n-button>
          </div>
        </header>

        <section class="profile-strip">
          <div class="profile-fact">
            <n-icon><Server /></n-icon>
            <span>平台</span>
            <strong>{{ currentProfile?.openwrtTarget || 'qualcommax/ipq807x' }}</strong>
          </div>
          <div class="profile-fact">
            <n-icon><HardDrive /></n-icon>
            <span>分区</span>
            <strong>{{ bootLayoutShort }}</strong>
          </div>
          <div class="profile-fact">
            <n-icon><PackageCheck /></n-icon>
            <span>本次预装</span>
            <strong>{{ effectivePackageCount.toLocaleString() }} 个包</strong>
          </div>
          <div class="profile-fact wide">
            <n-icon><Download /></n-icon>
            <span>镜像</span>
            <strong>{{ officialImageTypesText }}</strong>
          </div>
        </section>

        <main class="workspace">
          <n-tabs v-model:value="activeTab" type="line" animated class="workspace-tabs">
            <n-tab-pane name="device" tab="设备设置" class="scroll-pane">
              <div class="tab-heading">
                <div>
                  <h1>设备与系统设置</h1>
                  <p>{{ profileMetadata.title || 'Xiaomi AX9000' }} · {{ supportedDevicesText }}</p>
                </div>
                <n-tag type="success">{{ options.theme }} + {{ options.webServer }}</n-tag>
              </div>

              <div class="settings-layout device-layout">
                <section class="settings-section">
                  <div class="section-heading">
                    <n-icon><Router /></n-icon>
                    <h2>管理后台</h2>
                  </div>
                  <n-form :model="options" label-placement="top" size="small" class="control-grid three-columns">
                    <n-form-item label="主机名">
                      <n-input v-model:value="options.hostname" />
                    </n-form-item>
                    <n-form-item label="Root 密码">
                      <n-input v-model:value="options.rootPassword" type="password" show-password-on="click" />
                    </n-form-item>
                    <n-form-item label="快捷访问路径">
                      <n-input v-model:value="options.quickPath" placeholder="openwrt">
                        <template #suffix>/</template>
                      </n-input>
                    </n-form-item>
                    <n-form-item label="默认主题">
                      <n-select v-model:value="options.theme" :options="themeOptions" />
                    </n-form-item>
                    <n-form-item label="Web 服务器">
                      <n-select v-model:value="options.webServer" :options="webServerOptions" />
                    </n-form-item>
                    <n-form-item label="固件签名">
                      <n-input v-model:value="options.customSignature" placeholder="显示在 Powered by 后方" />
                    </n-form-item>
                  </n-form>
                  <div class="managed-package-row">
                    <span>自动预装</span>
                    <n-tag v-for="pkg in themeAndWebPackages" :key="pkg" size="tiny">{{ pkg }}</n-tag>
                    <n-switch
                      v-model:value="options.httpsAdmin"
                      size="small"
                      :disabled="!selectedWebServer?.supportsHttps"
                    >
                      <template #checked>HTTPS</template>
                      <template #unchecked>HTTP</template>
                    </n-switch>
                  </div>
                </section>

                <section class="settings-section">
                  <div class="section-heading">
                    <n-icon><ExternalLink /></n-icon>
                    <h2>作者与外链</h2>
                  </div>
                  <n-form :model="options" label-placement="top" size="small" class="control-grid">
                    <n-form-item label="作者名称">
                      <n-input v-model:value="options.authorName" placeholder="显示在系统概览中" />
                    </n-form-item>
                    <n-form-item label="作者外链">
                      <n-input v-model:value="options.authorUrl" placeholder="https://example.com" />
                    </n-form-item>
                  </n-form>
                  <div class="section-heading compact-heading">
                    <n-icon><Languages /></n-icon>
                    <h2>语言</h2>
                  </div>
                  <div class="language-controls">
                    <n-checkbox-group :value="options.installedLanguages" @update:value="updateInstalledLanguages">
                      <n-checkbox
                        v-for="language in languagePresets"
                        :key="language.id"
                        :value="language.id"
                        :disabled="language.builtin"
                      >
                        {{ language.title }}
                      </n-checkbox>
                    </n-checkbox-group>
                    <n-select v-model:value="options.defaultLanguage" :options="defaultLanguageOptions" size="small" />
                  </div>
                </section>

                <section class="settings-section feature-section">
                  <div class="section-heading">
                    <n-icon><Boxes /></n-icon>
                    <h2>功能组合</h2>
                  </div>
                  <div class="feature-grid">
                    <label v-for="feature in featurePresets" :key="feature.id" class="feature-toggle">
                      <div>
                        <strong>{{ feature.title }}</strong>
                        <span>{{ feature.description }}</span>
                        <small>{{ feature.packages.length }} 个自动包</small>
                      </div>
                      <n-switch :value="featureEnabled(feature.id)" @update:value="setFeatureEnabled(feature.id, $event)" />
                    </label>
                  </div>
                </section>

                <section class="settings-section system-section">
                  <div class="section-heading">
                    <n-icon><Shield /></n-icon>
                    <h2>防火墙后端</h2>
                  </div>
                  <n-radio-group v-model:value="options.firewallBackend" class="mode-segments">
                    <n-radio-button v-for="backend in firewallPresets" :key="backend.id" :value="backend.id">
                      {{ backend.title }}
                    </n-radio-button>
                  </n-radio-group>
                  <div class="backend-detail">
                    <strong>{{ selectedFirewall?.description }}</strong>
                    <span>{{ selectedFirewall?.packages.join(' · ') }}</span>
                  </div>
                  <n-form-item label="系统初始化脚本" class="script-field">
                    <n-input
                      v-model:value="options.initScript"
                      type="textarea"
                      :autosize="{ minRows: 4, maxRows: 8 }"
                      placeholder="#!/bin/sh"
                    />
                  </n-form-item>
                </section>
              </div>
            </n-tab-pane>

            <n-tab-pane name="packages" tab="软件包" class="package-pane">
              <div class="tab-heading package-heading">
                <div>
                  <h1>软件包与代理预设</h1>
                  <p>{{ catalogModeText }} · 本次固件共 {{ effectivePackageCount }} 个显式包</p>
                </div>
                <n-button :loading="syncingCatalog" @click="syncCatalog">
                  <template #icon><n-icon><RefreshCw /></n-icon></template>
                  同步软件库
                </n-button>
              </div>

              <n-tabs v-model:value="packageView" type="segment" animated class="package-subtabs">
                <n-tab-pane name="base" :tab="`基础包 ${selectedBaseCount}/${basePackages.length}`">
                  <div class="package-page">
                    <div class="package-page-heading">
                      <div>
                        <h2>基础包</h2>
                        <span>已选择 {{ selectedBaseCount }} 项，设备必需包不可取消</span>
                      </div>
                      <n-tag size="small" type="warning">{{ requiredPackageCount }} 个必需包</n-tag>
                    </div>
                    <div class="base-toolbar">
                      <n-input v-model:value="baseSearch" clearable size="small" placeholder="搜索基础包">
                        <template #prefix><n-icon><Search /></n-icon></template>
                      </n-input>
                      <n-tag size="small">{{ filteredBasePackages.length }} 个结果</n-tag>
                    </div>
                    <div class="base-package-list">
                      <label v-for="item in filteredBasePackages" :key="item.name" class="base-package-item">
                        <n-checkbox
                          :checked="isBaseSelected(item.name)"
                          :disabled="isRequiredPackage(item.name)"
                          @update:checked="toggleBasePackage(item.name, $event)"
                        />
                        <span>
                          <strong>{{ item.name }}</strong>
                          <small>{{ item.title }}</small>
                        </span>
                        <n-tag v-if="isRequiredPackage(item.name)" size="tiny" type="warning">必需</n-tag>
                      </label>
                    </div>
                  </div>
                </n-tab-pane>

                <n-tab-pane name="catalog" :tab="`软件目录 ${catalogChoices.length.toLocaleString()}`">
                  <div class="package-page">
                    <div class="package-page-heading">
                      <div>
                        <h2>软件目录</h2>
                        <span>已选择 {{ selectedCatalogCount }} 项，已隐藏基础包和代理预设包</span>
                      </div>
                      <n-tag v-if="catalog.generatedAt" size="small" type="success">已同步</n-tag>
                      <n-tag v-else size="small">精选目录</n-tag>
                    </div>

                    <div class="package-toolbar">
                      <n-input v-model:value="packageSearch" clearable placeholder="搜索中文名称、包名或用途">
                        <template #prefix><n-icon><Search /></n-icon></template>
                      </n-input>
                      <n-select v-model:value="packageSelection" :options="packageSelectionOptions" />
                      <n-select v-model:value="packageCategory" :options="packageCategoryOptions" />
                      <n-select v-model:value="packageSource" :options="packageSourceOptions" />
                      <n-tag size="small">{{ filteredPackages.length.toLocaleString() }} 个结果</n-tag>
                    </div>

                    <section class="catalog-panel">
                      <n-virtual-list
                        v-if="filteredPackages.length"
                        :items="filteredPackages"
                        :item-size="72"
                        key-field="name"
                        class="package-list"
                      >
                        <template #default="{ item }">
                          <div class="package-item" :class="{ selected: isCatalogChoiceSelected(item) }">
                            <n-checkbox
                              :checked="isCatalogChoiceChecked(item)"
                              :indeterminate="isCatalogChoiceIndeterminate(item)"
                              :disabled="isCatalogChoiceDisabled(item)"
                              @update:checked="toggleCatalogChoice(item, $event)"
                            />
                            <div class="package-copy">
                              <strong>{{ item.name }}</strong>
                              <span>{{ packageTitle(item) }}</span>
                              <code v-if="item.packages.length > 1">{{ item.packages.join(' + ') }}</code>
                            </div>
                            <n-tag v-if="isPresetManagedPackage(item.name)" size="tiny" type="info">自动管理</n-tag>
                            <n-tag v-else-if="item.packages.length > 1" size="tiny" type="success">{{ item.packages.length }} 个包</n-tag>
                            <n-tag v-else-if="item.application" size="tiny" type="info">应用</n-tag>
                            <n-tag v-else size="tiny">{{ item.source }}</n-tag>
                          </div>
                        </template>
                      </n-virtual-list>
                      <n-empty v-else description="没有符合条件的软件包" class="catalog-empty" />
                    </section>
                  </div>
                </n-tab-pane>

                <n-tab-pane name="proxies" :tab="`代理预设 ${options.proxyPresets.length}/${proxyPresets.length}`">
                  <div class="package-page">
                    <div class="package-page-heading">
                      <div>
                        <h2>代理预设</h2>
                        <span>已选择 {{ options.proxyPresets.length }} 项</span>
                      </div>
                      <n-tag size="small">{{ selectedFirewall?.title }}</n-tag>
                    </div>
                    <div class="proxy-grid">
                      <label
                        v-for="proxy in proxyPresets"
                        :key="proxy.id"
                        class="proxy-option"
                        :class="{ disabled: !proxyCompatible(proxy) }"
                      >
                        <n-checkbox
                          :checked="options.proxyPresets.includes(proxy.id)"
                          :disabled="!proxyCompatible(proxy)"
                          @update:checked="toggleProxy(proxy.id, $event)"
                        />
                        <div>
                          <strong>{{ proxy.title }}</strong>
                          <span>{{ proxy.description }}</span>
                          <code>{{ proxy.packages.join(' · ') }}</code>
                        </div>
                        <n-tag size="tiny">{{ proxy.packages.length }} 包</n-tag>
                      </label>
                    </div>
                    <div class="package-page-heading proxy-core-heading">
                      <div>
                        <h2>代理核心</h2>
                        <span>可独立选择、不安装或同时安装多个核心</span>
                      </div>
                      <n-tag size="small">已选择 {{ options.proxyCores.length }} 项</n-tag>
                    </div>
                    <div class="proxy-grid">
                      <label v-for="core in proxyCores" :key="core.id" class="proxy-option">
                        <n-checkbox
                          :checked="options.proxyCores.includes(core.id)"
                          @update:checked="toggleProxyCore(core.id, $event)"
                        />
                        <div>
                          <strong>{{ core.title }}</strong>
                          <span>{{ core.description }}</span>
                          <code>{{ core.packages.join(' · ') }}</code>
                        </div>
                      </label>
                    </div>
                  </div>
                </n-tab-pane>
              </n-tabs>
            </n-tab-pane>

            <n-tab-pane name="network" tab="网络与无线" class="scroll-pane">
              <div class="tab-heading">
                <div>
                  <h1>网络与无线设置</h1>
                  <p>首次启动时写入设备默认配置</p>
                </div>
              </div>

              <div class="settings-layout">
                <section class="settings-section">
                  <div class="section-heading"><n-icon><Network /></n-icon><h2>LAN 与 DHCP</h2></div>
                  <n-form :model="options" label-placement="top" size="small" class="control-grid">
                    <n-form-item label="后台 IPv4 地址"><n-input v-model:value="options.lanIp" /></n-form-item>
                    <n-form-item label="子网掩码"><n-input v-model:value="options.netmask" /></n-form-item>
                    <n-form-item v-if="options.bypassMode" label="IPv4 网关">
                      <n-input v-model:value="options.ipv4Gateway" placeholder="192.168.32.1" />
                    </n-form-item>
                  </n-form>
                  <div class="toggle-grid network-toggles">
                    <label class="toggle-row"><span>DHCP 服务</span><n-switch v-model:value="options.dhcpServer" size="small" /></label>
                    <label class="toggle-row"><span>IPv6</span><n-switch v-model:value="options.ipv6" size="small" /></label>
                    <label class="toggle-row"><span>旁路由模式</span><n-switch v-model:value="options.bypassMode" size="small" /></label>
                  </div>
                </section>

                <section class="settings-section">
                  <div class="section-heading"><n-icon><Wifi /></n-icon><h2>WAN 与 Wi-Fi</h2></div>
                  <n-form :model="options" label-placement="top" size="small" class="control-grid">
                    <n-form-item label="PPPoE 账号"><n-input v-model:value="options.pppoeUser" /></n-form-item>
                    <n-form-item label="PPPoE 密码"><n-input v-model:value="options.pppoePassword" type="password" show-password-on="click" /></n-form-item>
                    <n-form-item label="Wi-Fi 配置方式" style="grid-column: 1 / -1">
                      <n-radio-group v-model:value="options.wifiMode" class="mode-segments">
                        <n-radio-button value="band">按频段区分</n-radio-button>
                        <n-radio-button value="unified">全部统一</n-radio-button>
                        <n-radio-button value="wizard">首次启动向导</n-radio-button>
                      </n-radio-group>
                    </n-form-item>
                    <n-form-item v-if="options.wifiMode !== 'wizard'" label="Wi-Fi 基础名称">
                      <n-input v-model:value="options.wifiSsid" :placeholder="options.wifiMode === 'band' ? '自动生成 _2.4G 和 _5G' : ''" />
                    </n-form-item>
                    <n-form-item v-if="options.wifiMode !== 'wizard'" label="Wi-Fi 密码"><n-input v-model:value="options.wifiPassword" type="password" show-password-on="click" /></n-form-item>
                    <n-form-item v-if="options.exposePublic" label="WAN 开放端口">
                      <n-input v-model:value="options.exposedPorts" placeholder="22 80 443" />
                    </n-form-item>
                  </n-form>
                  <div class="toggle-grid">
                    <label class="toggle-row danger-toggle">
                      <span>允许 WAN 访问指定端口</span>
                      <n-switch v-model:value="options.exposePublic" size="small" />
                    </label>
                  </div>
                </section>
              </div>
            </n-tab-pane>

            <n-tab-pane name="sources" tab="软件源" class="scroll-pane">
              <div class="tab-heading">
                <div>
                  <h1>软件源</h1>
                  <p>运行时镜像单选，编译 feeds 可按需启用</p>
                </div>
                <div class="heading-actions">
                  <n-button @click="resetFeeds"><template #icon><n-icon><RotateCcw /></n-icon></template>恢复 feeds</n-button>
                  <n-button type="primary" :loading="syncingCatalog" @click="syncCatalog">
                    <template #icon><n-icon><RefreshCw /></n-icon></template>保存并同步
                  </n-button>
                </div>
              </div>

              <section class="runtime-mirror-section">
                <div class="section-heading">
                  <n-icon><Globe2 /></n-icon><h2>固件运行时软件镜像</h2>
                  <span class="section-note">仅保留一个运行时镜像地址</span>
                </div>
                <div class="runtime-mirror-list" role="radiogroup" aria-label="运行时软件镜像">
                  <button
                    v-for="mirror in runtimeMirrors"
                    :key="mirror.id"
                    type="button"
                    class="runtime-mirror-option"
                    :class="{
                      selected: options.runtimeMirror === mirror.id,
                      unsupported: mirrorChecks[mirror.id]?.supported === false
                    }"
                    :disabled="checkingMirror !== null"
                    :aria-checked="options.runtimeMirror === mirror.id"
                    :title="mirrorChecks[mirror.id]?.message || mirror.description"
                    role="radio"
                    @click="selectRuntimeMirror(mirror.id)"
                  >
                    <span class="runtime-mirror-option-head">
                      <strong>{{ mirror.title }}</strong>
                      <span class="runtime-mirror-option-tags">
                        <n-tag size="tiny">{{ mirror.region }}</n-tag>
                        <n-tag v-if="checkingMirror === mirror.id" size="tiny" type="warning">检查中</n-tag>
                        <n-tag v-else-if="mirrorChecks[mirror.id]?.supported === true" size="tiny" type="success">可用</n-tag>
                        <n-tag v-else-if="mirrorChecks[mirror.id]?.supported === false" size="tiny" type="error">不支持</n-tag>
                      </span>
                    </span>
                    <span>{{ mirror.description }}</span>
                  </button>
                </div>
                <div class="runtime-address-panel">
                  <div>
                    <span class="mirror-field-label">运行时地址</span>
                    <p v-if="options.runtimeMirror !== 'custom'" class="runtime-address-value">{{ selectedRuntimeMirrorAddress || '由构建源码中的版本与架构路径生成' }}</p>
                    <n-input
                      v-else
                      v-model:value="options.customMirrorUrl"
                      placeholder="https://mirror.example.com/openwrt"
                    />
                  </div>
                  <n-button
                    v-if="options.runtimeMirror !== 'custom'"
                    :disabled="!selectedRuntimeMirrorAddress"
                    @click="editRuntimeMirror"
                  >使用此地址编辑</n-button>
                </div>
              </section>

              <section class="feed-editor-section">
                <div class="section-heading"><n-icon><Boxes /></n-icon><h2>编译 feeds 源码仓库</h2></div>
                <div class="feed-editor">
                  <div class="feed-row feed-header">
                    <span>启用</span><span>名称</span><span>Git 地址</span><span>分支</span><span>类型</span><span></span>
                  </div>
                  <div v-for="(feed, index) in options.feeds" :key="`${feed.builtin ? 'builtin' : 'custom'}-${index}`" class="feed-row">
                    <n-switch v-model:value="feed.enabled" size="small" />
                    <n-input v-model:value="feed.name" size="small" :disabled="feed.builtin" />
                    <n-input v-model:value="feed.url" size="small" />
                    <n-input v-model:value="feed.branch" size="small" />
                    <n-tag size="small" :type="feed.builtin ? 'info' : 'warning'">{{ feed.builtin ? '内置' : '自定义' }}</n-tag>
                    <n-tooltip>
                      <template #trigger>
                        <n-button quaternary circle size="small" :disabled="feed.builtin" @click="removeFeed(index)">
                          <template #icon><n-icon><Trash2 /></n-icon></template>
                        </n-button>
                      </template>
                      删除软件源
                    </n-tooltip>
                  </div>
                  <n-button dashed class="add-feed" @click="addFeed"><template #icon><n-icon><Plus /></n-icon></template>添加软件源</n-button>
                </div>
              </section>

              <section v-if="catalog.sources.length" class="source-status">
                <div v-for="source in catalog.sources" :key="source.name" class="source-status-item">
                  <div><strong>{{ source.label || source.name }}</strong><span>{{ source.revision }}</span></div>
                  <n-tag type="success">{{ source.count.toLocaleString() }} 项</n-tag>
                </div>
              </section>
            </n-tab-pane>

            <n-tab-pane name="outputs" tab="产物与日志" class="output-pane">
              <div class="tab-heading">
                <div>
                  <h1>构建产物与日志</h1>
                  <p>{{ statusText }}<template v-if="status.startedAt"> · {{ formatTime(status.startedAt) }}</template></p>
                </div>
                <n-button v-if="status.running" type="error" :loading="status.stopping" @click="stopBuild">
                  <template #icon><n-icon><Square /></n-icon></template>停止构建
                </n-button>
              </div>

              <div class="output-layout">
                <section class="output-section firmware-details">
                  <div class="section-heading"><n-icon><Server /></n-icon><h2>固件信息</h2></div>
                  <n-descriptions :column="2" bordered label-placement="left" size="small">
                    <n-descriptions-item label="型号">{{ profileMetadata.title || 'Xiaomi AX9000' }}</n-descriptions-item>
                    <n-descriptions-item label="设备 ID">{{ supportedDevicesText }}</n-descriptions-item>
                    <n-descriptions-item label="平台">{{ currentProfile?.openwrtTarget }}</n-descriptions-item>
                    <n-descriptions-item label="分支">{{ currentProfile?.repoBranch }}</n-descriptions-item>
                    <n-descriptions-item label="启动布局">{{ bootLayoutText }}</n-descriptions-item>
                    <n-descriptions-item label="后台">{{ options.lanIp }} / {{ normalizedQuickPath }}/</n-descriptions-item>
                    <n-descriptions-item label="语言">{{ selectedLanguageText }}</n-descriptions-item>
                    <n-descriptions-item label="防火墙">{{ selectedFirewall?.title }}</n-descriptions-item>
                    <n-descriptions-item label="镜像类型" :span="2">{{ officialImageTypesText }}</n-descriptions-item>
                  </n-descriptions>
                </section>

                <section class="output-section artifacts-section">
                  <div class="section-heading"><n-icon><Archive /></n-icon><h2>下载固件包</h2></div>
                  <n-empty v-if="!artifacts.length" description="暂无 ZIP 构建产物" />
                  <div v-else class="downloads">
                    <div v-for="file in artifacts" :key="file.name" class="download-row">
                      <div class="download-copy"><strong>{{ file.name }}</strong><span>{{ formatSize(file.size) }} · {{ file.typeLabel }}</span></div>
                      <n-button tag="a" :href="artifactUrl(file.name)" :download="file.name" type="primary" secondary>
                        <template #icon><n-icon><Download /></n-icon></template>下载 ZIP
                      </n-button>
                    </div>
                  </div>
                </section>
              </div>

              <n-collapse v-model:expanded-names="outputSections" class="log-collapse">
                <n-collapse-item name="logs">
                  <template #header>
                    <div class="log-header">
                      <n-icon><Terminal /></n-icon>
                      <strong>实时日志</strong>
                      <span>{{ status.running ? '构建输出持续写入中' : '最近一次构建输出' }}</span>
                      <n-tag size="small" :type="status.running ? 'success' : 'default'">{{ logs.length }} 行</n-tag>
                    </div>
                  </template>
                  <pre ref="logRef" class="logs"><span v-if="!logs.length" class="log-placeholder">等待构建任务</span><span v-for="line in logs" :key="line.ts + line.text" class="log-line"><time>[{{ formatTime(line.ts) }}]</time> {{ line.text }}</span></pre>
                </n-collapse-item>
              </n-collapse>
            </n-tab-pane>
          </n-tabs>
        </main>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import {
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NCollapse,
  NCollapseItem,
  NConfigProvider,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NInputNumber,
  NMessageProvider,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  NTooltip,
  NVirtualList,
  createDiscreteApi
} from 'naive-ui';
import {
  Archive,
  Boxes,
  Download,
  ExternalLink,
  Globe2,
  HardDrive,
  Languages,
  Network,
  PackageCheck,
  Plus,
  RefreshCw,
  RotateCcw,
  Router,
  Search,
  Server,
  Settings,
  Shield,
  Square,
  Terminal,
  Trash2,
  Wifi
} from 'lucide-vue-next';

interface FeedSource {
  name: string;
  label: string;
  url: string;
  branch: string;
  kind: string;
  builtin: boolean;
  enabled: boolean;
}

interface PackagePreset {
  id: string;
  title: string;
  description: string;
  packages: string[];
  zhCnPackages?: string[];
  firewallBackends?: string[];
  recommendedCores?: string[];
}

interface ThemePreset extends PackagePreset {
  mediaUrl: string;
}

interface WebServerPreset extends PackagePreset {
  httpsPackages: string[];
  supportsHttps: boolean;
}

interface FirewallPreset extends PackagePreset {
  disabledPackages: string[];
  requiresKernelIpv6: boolean;
}

interface LanguagePreset extends PackagePreset {
  builtin: boolean;
}

interface RuntimeMirror {
  id: string;
  title: string;
  region: string;
  description: string;
  baseUrl: string;
}

interface MirrorCompatibility {
  mirrorId: string;
  checked: boolean;
  supported: boolean | null;
  message: string;
  checks: Array<{ url: string; ok: boolean; status: number | null; error?: string }>;
}

interface ProfilePresets {
  themes?: ThemePreset[];
  webServers?: WebServerPreset[];
  features?: PackagePreset[];
  proxies?: PackagePreset[];
  proxyCores?: PackagePreset[];
  firewallBackends?: FirewallPreset[];
  languages?: LanguagePreset[];
  runtimeMirrors?: RuntimeMirror[];
  requiredPackages?: string[];
  packageLabels?: Record<string, string>;
  zhCnPackageTranslations?: Record<string, string>;
  packageGroups?: Record<string, string[]>;
}

interface ProfileMetadata {
  title?: string;
  profileId?: string;
  supportedDevices?: string[];
  bootLayout?: string;
  rootfsPartition?: string;
  rootfsSize?: string;
  upstreamReference?: { imageTypes?: string[]; devicePackages?: string[] };
  notes?: string[];
}

interface Profile {
  name: string;
  targetDir: string;
  openwrtTarget: string;
  deviceId: string;
  repoBranch: string;
  packages: string[];
  metadata: ProfileMetadata;
  presets: ProfilePresets;
  defaultOptions: Partial<BuildOptions>;
  feeds: FeedSource[];
}

interface PackageItem {
  name: string;
  title: string;
  category: string;
  source: string;
}

interface CatalogChoice extends PackageItem {
  packages: string[];
  application: boolean;
}

interface CatalogSource {
  name: string;
  label: string;
  revision: string;
  count: number;
}

interface PackageCatalog {
  mode: 'curated' | 'synced';
  generatedAt: string | null;
  sources: CatalogSource[];
  total: number;
  packages: PackageItem[];
}

interface LogLine { ts: string; text: string }

interface BuildStatus {
  running: boolean;
  stopping: boolean;
  profile: string | null;
  jobs: number;
  clean: boolean;
  startedAt: string | null;
  endedAt: string | null;
  exitCode: number | null;
  logs: LogLine[];
}

interface Artifact {
  name: string;
  size: number;
  type: string;
  typeLabel: string;
  modifiedAt: string;
}

type FeatureKey = 'docker' | 'storeOs' | 'nasMode' | 'rndis';

interface BuildOptions {
  basePackages: string[] | null;
  selectedPackages: string[];
  proxyPresets: string[];
  proxyCores: string[];
  feeds: FeedSource[];
  lanIp: string;
  netmask: string;
  rootPassword: string;
  theme: string;
  docker: boolean;
  storeOs: boolean;
  nasMode: boolean;
  webServer: string;
  quickPath: string;
  httpsAdmin: boolean;
  installedLanguages: string[];
  defaultLanguage: string;
  firewallBackend: string;
  runtimeMirror: string;
  customMirrorUrl: string;
  ipv6: boolean;
  bypassMode: boolean;
  ipv4Gateway: string;
  dhcpServer: boolean;
  pppoeUser: string;
  pppoePassword: string;
  wifiMode: 'band' | 'unified' | 'wizard';
  wifiSsid: string;
  wifiPassword: string;
  exposePublic: boolean;
  exposedPorts: string;
  rndis: boolean;
  hostname: string;
  customSignature: string;
  authorName: string;
  authorUrl: string;
  initScript: string;
}

interface SavedConfigResponse {
  saved: boolean;
  options: BuildOptions | null;
  jobs: number;
  clean: boolean;
}

const STORAGE_KEY = 'openwrt-build-options';
const { message } = createDiscreteApi(['message']);
const profiles = ref<Profile[]>([]);
const selectedProfile = ref('ax9000');
const activeTab = ref('device');
const jobs = ref(0);
const clean = ref(false);
const rememberOptions = ref(false);
const persistenceReady = ref(false);
const artifacts = ref<Artifact[]>([]);
const logs = ref<LogLine[]>([]);
const logRef = ref<HTMLElement | null>(null);
const packageSearch = ref('');
const baseSearch = ref('');
const packageSelection = ref<'all' | 'selected' | 'unselected'>('all');
const packageCategory = ref('all');
const packageSource = ref('all');
const syncingCatalog = ref(false);
const checkingMirror = ref<string | null>(null);
const mirrorChecks = ref<Record<string, MirrorCompatibility>>({});
const packageView = ref<'base' | 'catalog' | 'proxies'>('base');
const outputSections = ref<string[]>(['logs']);
const catalog = ref<PackageCatalog>({ mode: 'curated', generatedAt: null, sources: [], total: 0, packages: [] });
const status = ref<BuildStatus>({
  running: false,
  stopping: false,
  profile: null,
  jobs: 0,
  clean: false,
  startedAt: null,
  endedAt: null,
  exitCode: null,
  logs: []
});

function createDefaultOptions(): BuildOptions {
  return {
    basePackages: null,
    selectedPackages: [],
    proxyPresets: [],
    proxyCores: [],
    feeds: [],
    lanIp: '192.168.32.1',
    netmask: '255.255.255.0',
    rootPassword: 'password',
    theme: 'Argon',
    docker: false,
    storeOs: false,
    nasMode: false,
    webServer: 'Nginx',
    quickPath: 'openwrt',
    httpsAdmin: false,
    installedLanguages: ['en', 'zh_cn'],
    defaultLanguage: 'auto',
    firewallBackend: 'firewall4',
    runtimeMirror: 'build-default',
    customMirrorUrl: '',
    ipv6: false,
    bypassMode: false,
    ipv4Gateway: '',
    dhcpServer: true,
    pppoeUser: '',
    pppoePassword: '',
    wifiMode: 'band',
    wifiSsid: '',
    wifiPassword: '',
    exposePublic: false,
    exposedPorts: '',
    rndis: false,
    hostname: 'OpenWRT',
    customSignature: '',
    authorName: '',
    authorUrl: '',
    initScript: ''
  };
}

const options = reactive<BuildOptions>(createDefaultOptions());
const currentProfile = computed(() => profiles.value.find((profile) => profile.name === selectedProfile.value));
const profileMetadata = computed(() => currentProfile.value?.metadata ?? {});
const presets = computed<ProfilePresets>(() => currentProfile.value?.presets ?? {});
const themePresets = computed(() => presets.value.themes ?? []);
const webServerPresets = computed(() => presets.value.webServers ?? []);
const featurePresets = computed(() => presets.value.features ?? []);
const proxyPresets = computed(() => presets.value.proxies ?? []);
const proxyCores = computed(() => presets.value.proxyCores ?? []);
const firewallPresets = computed(() => presets.value.firewallBackends ?? []);
const languagePresets = computed(() => presets.value.languages ?? []);
const runtimeMirrors = computed(() => presets.value.runtimeMirrors ?? []);
const selectedRuntimeMirror = computed(() => runtimeMirrors.value.find((mirror) => mirror.id === options.runtimeMirror));
const selectedRuntimeMirrorAddress = computed(() => options.runtimeMirror === 'custom'
  ? options.customMirrorUrl
  : selectedRuntimeMirror.value?.baseUrl || '');
const themeOptions = computed(() => themePresets.value.map((item) => ({ label: item.title, value: item.id })));
const webServerOptions = computed(() => webServerPresets.value.map((item) => ({ label: item.title, value: item.id })));
const selectedWebServer = computed(() => webServerPresets.value.find((item) => item.id === options.webServer));
const selectedTheme = computed(() => themePresets.value.find((item) => item.id === options.theme));
const selectedFirewall = computed(() => firewallPresets.value.find((item) => item.id === options.firewallBackend));
const selectedProxyPresets = computed(() => proxyPresets.value.filter((item) => options.proxyPresets.includes(item.id)));
const requiredPackageSet = computed(() => new Set(presets.value.requiredPackages ?? []));
const requiredPackageCount = computed(() => requiredPackageSet.value.size);
const basePackages = computed(() => currentProfile.value?.packages.filter((pkg) => !pkg.startsWith('-')) ?? []);
const basePackageSet = computed(() => new Set(basePackages.value));
const selectedBaseSet = computed(() => new Set(options.basePackages ?? []));
const selectedBaseCount = computed(() => selectedBaseSet.value.size);
const selectedPackageSet = computed(() => new Set(options.selectedPackages));
const packageMap = computed(() => new Map(catalog.value.packages.map((item) => [item.name, item])));
const baseManagedPackageSet = computed(() => {
  const packages = new Set(basePackages.value);
  for (const [basePackage, translation] of Object.entries(presets.value.zhCnPackageTranslations ?? {})) {
    if (basePackageSet.value.has(basePackage)) packages.add(translation);
  }
  return packages;
});
const proxyManagedPackageSet = computed(() => {
  const packages = new Set<string>();
  for (const proxy of proxyPresets.value) {
    proxy.packages.forEach((pkg) => packages.add(pkg));
    proxy.zhCnPackages?.forEach((pkg) => packages.add(pkg));
  }
  for (const core of proxyCores.value) core.packages.forEach((pkg) => packages.add(pkg));
  return packages;
});
const catalogVisiblePackages = computed(() => catalog.value.packages.filter((item) => (
  !baseManagedPackageSet.value.has(item.name) && !proxyManagedPackageSet.value.has(item.name)
)));
const catalogChoices = computed<CatalogChoice[]>(() => {
  const groups = presets.value.packageGroups ?? {};
  const consumed = new Set<string>();
  const choices: CatalogChoice[] = [];

  for (const item of catalogVisiblePackages.value) {
    if (!item.name.startsWith('luci-app-')) continue;
    const packages = [...new Set([item.name, ...(groups[item.name] ?? [])])];
    packages.slice(1).forEach((name) => consumed.add(name));
    choices.push({ ...item, packages, application: true });
  }
  for (const item of catalogVisiblePackages.value) {
    if (item.name.startsWith('luci-app-') || consumed.has(item.name)) continue;
    choices.push({ ...item, packages: [item.name], application: false });
  }
  return choices.sort((left, right) => (
    left.category.localeCompare(right.category, 'zh-CN')
    || left.name.localeCompare(right.name, 'en')
  ));
});

const supportedDevicesText = computed(() => profileMetadata.value.supportedDevices?.join(', ') || currentProfile.value?.deviceId || 'xiaomi_ax9000');
const bootLayoutText = computed(() => profileMetadata.value.bootLayout === 'large-rootfs'
  ? `大分区，升级写入 ${profileMetadata.value.rootfsPartition || 'rootfs'}（${profileMetadata.value.rootfsSize || '按当前 MIBIB'}）`
  : profileMetadata.value.bootLayout || '按设备默认布局');
const bootLayoutShort = computed(() => profileMetadata.value.bootLayout === 'large-rootfs' ? '单 rootfs 大分区' : '设备默认');
const officialImageTypesText = computed(() => profileMetadata.value.upstreamReference?.imageTypes?.join(' / ') || 'sysupgrade / factory');
const normalizedQuickPath = computed(() => options.quickPath.replace(/^\/+|\/+$/g, '') || 'openwrt');

const statusText = computed(() => {
  if (status.value.stopping) return '正在停止';
  if (status.value.running) return '构建中';
  if (status.value.exitCode === 0) return '构建完成';
  if (status.value.exitCode !== null) return '构建失败';
  return '空闲';
});
const statusTagType = computed(() => {
  if (status.value.running) return 'warning';
  if (status.value.exitCode === 0) return 'success';
  if (status.value.exitCode !== null) return 'error';
  return 'default';
});
const catalogModeText = computed(() => catalog.value.mode === 'synced'
  ? `已从 ${catalog.value.sources.length} 个源同步 ${catalog.value.total.toLocaleString()} 项`
  : `精选目录 ${catalog.value.total.toLocaleString()} 项，可同步全部 feeds`);

const defaultLanguageOptions = computed(() => [
  { label: '自动匹配浏览器', value: 'auto' },
  ...languagePresets.value
    .filter((item) => options.installedLanguages.includes(item.id))
    .map((item) => ({ label: item.title, value: item.id }))
]);
const selectedLanguageText = computed(() => options.defaultLanguage === 'auto'
  ? '自动'
  : languagePresets.value.find((item) => item.id === options.defaultLanguage)?.title || options.defaultLanguage);

const allPresetManagedPackages = computed(() => {
  const packages = new Set<string>();
  const groups = [themePresets.value, webServerPresets.value, featurePresets.value, proxyPresets.value, proxyCores.value, firewallPresets.value, languagePresets.value];
  for (const group of groups) {
    for (const entry of group) {
      entry.packages.forEach((pkg) => packages.add(pkg));
      entry.zhCnPackages?.forEach((pkg) => packages.add(pkg));
      if ('httpsPackages' in entry) (entry as WebServerPreset).httpsPackages.forEach((pkg) => packages.add(pkg));
      if ('disabledPackages' in entry) (entry as FirewallPreset).disabledPackages.forEach((pkg) => packages.add(pkg));
    }
  }
  Object.values(presets.value.zhCnPackageTranslations ?? {}).forEach((pkg) => packages.add(pkg));
  return packages;
});

const activeManagedPackages = computed(() => {
  const packages = new Set<string>();
  selectedTheme.value?.packages.forEach((pkg) => packages.add(pkg));
  selectedWebServer.value?.packages.forEach((pkg) => packages.add(pkg));
  if (options.httpsAdmin) selectedWebServer.value?.httpsPackages.forEach((pkg) => packages.add(pkg));
  selectedFirewall.value?.packages.forEach((pkg) => packages.add(pkg));
  for (const feature of featurePresets.value) {
    if (!featureEnabled(feature.id)) continue;
    feature.packages.forEach((pkg) => packages.add(pkg));
    if (options.installedLanguages.includes('zh_cn')) feature.zhCnPackages?.forEach((pkg) => packages.add(pkg));
  }
  for (const proxy of selectedProxyPresets.value) {
    proxy.packages.forEach((pkg) => packages.add(pkg));
    if (options.installedLanguages.includes('zh_cn')) proxy.zhCnPackages?.forEach((pkg) => packages.add(pkg));
  }
  for (const core of proxyCores.value) {
    if (options.proxyCores.includes(core.id)) core.packages.forEach((pkg) => packages.add(pkg));
  }
  for (const language of languagePresets.value) {
    if (options.installedLanguages.includes(language.id)) language.packages.forEach((pkg) => packages.add(pkg));
  }
  if (options.installedLanguages.includes('zh_cn')) {
    for (const [basePackage, translation] of Object.entries(presets.value.zhCnPackageTranslations ?? {})) {
      if (selectedBaseSet.value.has(basePackage) || selectedPackageSet.value.has(basePackage)) packages.add(translation);
    }
  }
  return packages;
});

const themeAndWebPackages = computed(() => {
  const packages = new Set<string>();
  selectedTheme.value?.packages.forEach((pkg) => packages.add(pkg));
  selectedWebServer.value?.packages.forEach((pkg) => packages.add(pkg));
  if (options.httpsAdmin) selectedWebServer.value?.httpsPackages.forEach((pkg) => packages.add(pkg));
  return [...packages];
});
const effectivePackageCount = computed(() => new Set([...(options.basePackages ?? []), ...options.selectedPackages, ...activeManagedPackages.value]).size);

const basePackageItems = computed(() => basePackages.value
  .map((name) => ({ name, title: presets.value.packageLabels?.[name] || packageMap.value.get(name)?.title || '系统基础包' }))
  .sort((left, right) => (
    Number(isRequiredPackage(right.name)) - Number(isRequiredPackage(left.name))
    || left.name.localeCompare(right.name, 'en')
  )));
const filteredBasePackages = computed(() => {
  const query = baseSearch.value.trim().toLowerCase();
  if (!query) return basePackageItems.value;
  return basePackageItems.value.filter((item) => item.name.toLowerCase().includes(query) || item.title.toLowerCase().includes(query));
});

const packageCategoryOptions = computed(() => {
  const counts = new Map<string, number>();
  for (const item of catalogChoices.value) counts.set(item.category, (counts.get(item.category) || 0) + 1);
  return [
    { label: `全部分类 (${catalogChoices.value.length.toLocaleString()})`, value: 'all' },
    ...Array.from(counts.entries()).sort(([left], [right]) => left.localeCompare(right, 'zh-CN')).map(([category, count]) => ({ label: `${category} (${count})`, value: category }))
  ];
});
const packageSourceOptions = computed(() => [
  { label: '全部软件源', value: 'all' },
  ...Array.from(new Set(catalogChoices.value.map((item) => item.source))).sort().map((source) => ({ label: source, value: source }))
]);
const packageSelectionOptions = computed(() => [
  { label: `全部状态 (${catalogChoices.value.length.toLocaleString()})`, value: 'all' },
  { label: `已选择 (${selectedCatalogCount.value.toLocaleString()})`, value: 'selected' },
  { label: `未选择 (${Math.max(0, catalogChoices.value.length - selectedCatalogCount.value).toLocaleString()})`, value: 'unselected' }
]);
const selectedCatalogCount = computed(() => catalogChoices.value.filter(isCatalogChoiceSelected).length);
const filteredPackages = computed(() => {
  const query = packageSearch.value.trim().toLowerCase();
  return catalogChoices.value.filter((item) => {
    const selected = isCatalogChoiceSelected(item);
    if (packageSelection.value === 'selected' && !selected) return false;
    if (packageSelection.value === 'unselected' && selected) return false;
    if (packageCategory.value !== 'all' && item.category !== packageCategory.value) return false;
    if (packageSource.value !== 'all' && item.source !== packageSource.value) return false;
    if (!query) return true;
    return item.packages.some((name) => name.toLowerCase().includes(query)) || packageTitle(item).toLowerCase().includes(query) || item.category.toLowerCase().includes(query);
  });
});

function packageTitle(item: PackageItem) {
  return item.title || presets.value.packageLabels?.[item.name] || item.category || '软件包';
}
function featureEnabled(id: string) { return Boolean(options[id as FeatureKey]); }
function setFeatureEnabled(id: string, value: boolean) { options[id as FeatureKey] = value; }
function isRequiredPackage(name: string) { return requiredPackageSet.value.has(name); }
function isBasePackage(name: string) { return basePackageSet.value.has(name); }
function isBaseSelected(name: string) { return selectedBaseSet.value.has(name); }
function isPresetManagedPackage(name: string) { return allPresetManagedPackages.value.has(name); }
function proxyForPackage(name: string) { return proxyPresets.value.find((item) => item.packages[0] === name); }
function proxyCompatible(proxy: PackagePreset) { return proxy.firewallBackends?.includes(options.firewallBackend) ?? true; }

function toggleBasePackage(name: string, checked: boolean) {
  if (isRequiredPackage(name)) return;
  const packages = options.basePackages ?? [];
  const index = packages.indexOf(name);
  if (checked && index === -1) packages.push(name);
  if (!checked && index !== -1) packages.splice(index, 1);
  options.basePackages = packages;
}
function toggleProxy(id: string, checked: boolean) {
  const proxy = proxyPresets.value.find((item) => item.id === id);
  if (!proxy || !proxyCompatible(proxy)) return;
  const index = options.proxyPresets.indexOf(id);
  if (checked && index === -1) options.proxyPresets.push(id);
  if (!checked && index !== -1) options.proxyPresets.splice(index, 1);
  if (checked) proxy.recommendedCores?.forEach((core) => {
    if (!options.proxyCores.includes(core)) options.proxyCores.push(core);
  });
}
function toggleProxyCore(id: string, checked: boolean) {
  const index = options.proxyCores.indexOf(id);
  if (checked && index === -1) options.proxyCores.push(id);
  if (!checked && index !== -1) options.proxyCores.splice(index, 1);
}
function isPackageChecked(name: string) {
  const proxy = proxyForPackage(name);
  if (proxy) return options.proxyPresets.includes(proxy.id);
  return isBaseSelected(name) || selectedPackageSet.value.has(name) || activeManagedPackages.value.has(name);
}
function isPackageDisabled(name: string) {
  if (isRequiredPackage(name)) return true;
  const proxy = proxyForPackage(name);
  if (proxy) return !proxyCompatible(proxy);
  return isPresetManagedPackage(name);
}
function isCatalogChoiceChecked(item: CatalogChoice) { return item.packages.every(isPackageChecked); }
function isCatalogChoiceSelected(item: CatalogChoice) { return item.packages.some(isPackageChecked); }
function isCatalogChoiceIndeterminate(item: CatalogChoice) { return isCatalogChoiceSelected(item) && !isCatalogChoiceChecked(item); }
function isCatalogChoiceDisabled(item: CatalogChoice) { return item.packages.some(isPackageDisabled); }
function toggleCatalogChoice(item: CatalogChoice, checked: boolean) {
  item.packages.forEach((name) => toggleCatalogPackage(name, checked));
}
function toggleCatalogPackage(name: string, checked: boolean) {
  if (isBasePackage(name)) {
    toggleBasePackage(name, checked);
    return;
  }
  const proxy = proxyForPackage(name);
  if (proxy) {
    toggleProxy(proxy.id, checked);
    return;
  }
  if (isPresetManagedPackage(name)) return;
  const index = options.selectedPackages.indexOf(name);
  if (checked && index === -1) options.selectedPackages.push(name);
  if (!checked && index !== -1) options.selectedPackages.splice(index, 1);
}
function updateInstalledLanguages(values: Array<string | number>) {
  const languages = values.map(String);
  if (!languages.includes('en')) languages.unshift('en');
  options.installedLanguages = [...new Set(languages)];
  if (options.defaultLanguage !== 'auto' && !options.installedLanguages.includes(options.defaultLanguage)) options.defaultLanguage = 'auto';
}

function editRuntimeMirror() {
  if (!selectedRuntimeMirrorAddress.value) return;
  options.customMirrorUrl = selectedRuntimeMirrorAddress.value;
  options.runtimeMirror = 'custom';
}

async function selectRuntimeMirror(mirrorId: string) {
  if (mirrorId === 'build-default' || mirrorId === 'custom') {
    options.runtimeMirror = mirrorId;
    return;
  }
  checkingMirror.value = mirrorId;
  try {
    const result = await api<MirrorCompatibility>(`/api/runtime-mirror/${selectedProfile.value}/${mirrorId}`);
    mirrorChecks.value = { ...mirrorChecks.value, [mirrorId]: result };
    if (result.supported) {
      options.runtimeMirror = mirrorId;
      const title = runtimeMirrors.value.find((item) => item.id === mirrorId)?.title || mirrorId;
      message.success(`${title}支持当前固件`);
    } else {
      if (options.runtimeMirror === mirrorId) options.runtimeMirror = 'build-default';
      message.warning(result.message);
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '软件镜像检查失败');
  } finally {
    checkingMirror.value = null;
  }
}

function cloneFeeds(feeds: FeedSource[]) { return feeds.map((feed) => ({ ...feed })); }
function effectiveFeeds() {
  return options.feeds
    .filter((feed) => feed.builtin || feed.url.trim())
    .map((feed) => ({ ...feed, name: feed.name.trim(), url: feed.url.trim(), branch: feed.branch.trim() || 'main' }));
}
function addFeed() {
  let suffix = 1;
  const names = new Set(options.feeds.map((feed) => feed.name));
  while (names.has(`custom${suffix}`)) suffix += 1;
  options.feeds.push({ name: `custom${suffix}`, label: `自定义源 ${suffix}`, url: '', branch: 'main', kind: 'custom', builtin: false, enabled: true });
}
function removeFeed(index: number) { if (!options.feeds[index]?.builtin) options.feeds.splice(index, 1); }
function resetFeeds() { options.feeds = cloneFeeds(currentProfile.value?.feeds || []); message.success('已恢复默认编译 feeds'); }

function formatTime(value: string) { return new Date(value).toLocaleString('zh-CN'); }
function formatSize(size: number) {
  if (size > 1024 * 1024 * 1024) return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
  if (size > 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size > 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}
function artifactUrl(name: string) { return `/artifacts/${selectedProfile.value}/${encodeURIComponent(name)}`; }

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = Array.isArray(body.detail) ? body.detail.map((item: { msg?: string }) => item.msg || String(item)).join('；') : body.detail;
    throw new Error(detail || body.message || response.statusText);
  }
  return response.json();
}

function normalizeOptions(source: Partial<BuildOptions>) {
  const defaults = createDefaultOptions();
  Object.assign(options, defaults, source);
  options.selectedPackages = Array.isArray(source.selectedPackages) ? [...new Set(source.selectedPackages)] : [];
  options.proxyPresets = Array.isArray(source.proxyPresets) ? [...new Set(source.proxyPresets)] : [];
  const legacyCores: Record<string, string[]> = {
    passwall: ['sing-box'], passwall2: ['xray-core', 'sing-box'], homeproxy: ['sing-box'], openclash: ['mihomo'], v2raya: ['xray-core']
  };
  options.proxyCores = Array.isArray(source.proxyCores)
    ? [...new Set(source.proxyCores)]
    : [...new Set(options.proxyPresets.flatMap((id) => legacyCores[id] ?? []))];
  options.installedLanguages = Array.isArray(source.installedLanguages) ? [...new Set(source.installedLanguages)] : ['en', 'zh_cn'];
  if (!options.installedLanguages.includes('en')) options.installedLanguages.unshift('en');
  options.basePackages = Array.isArray(source.basePackages) ? [...new Set(source.basePackages)] : null;
  options.feeds = Array.isArray(source.feeds) ? cloneFeeds(source.feeds) : [];
  if (options.runtimeMirror !== 'custom') options.customMirrorUrl = '';
  normalizeAuthorLink();
}

function isPlainHttpsUrl(value: string) {
  try {
    const parsed = new URL(value.trim());
    return parsed.protocol === 'https:' && Boolean(parsed.hostname) && !parsed.username && !parsed.password && !parsed.search && !parsed.hash;
  } catch {
    return false;
  }
}

function normalizeAuthorLink() {
  if (options.authorName.trim() && isPlainHttpsUrl(options.authorUrl)) return;
  options.authorName = '';
  options.authorUrl = '';
}

function loadLegacyRememberedOptions(): boolean {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return false;
  try {
    const raw = JSON.parse(saved) as Partial<BuildOptions> & { internetPlugins?: string[]; customPackages?: string };
    const legacyProxyIds: Record<string, string> = {
      PassWall: 'passwall', PassWall2: 'passwall2', HomeProxy: 'homeproxy', OpenClash: 'openclash', v2rayA: 'v2raya'
    };
    const legacyPackages: Record<string, string> = {
      'luci-app-passwall': 'passwall', 'luci-app-passwall2': 'passwall2', 'luci-app-homeproxy': 'homeproxy', 'luci-app-openclash': 'openclash', 'luci-app-v2raya': 'v2raya'
    };
    const migrated = { ...raw };
    delete migrated.internetPlugins;
    delete migrated.customPackages;
    const proxies = new Set(migrated.proxyPresets || []);
    raw.internetPlugins?.forEach((name) => { if (legacyProxyIds[name]) proxies.add(legacyProxyIds[name]); });
    migrated.selectedPackages = (migrated.selectedPackages || []).filter((name) => {
      const preset = legacyPackages[name];
      if (preset) proxies.add(preset);
      return !preset;
    });
    migrated.proxyPresets = [...proxies];
    normalizeOptions(migrated);
    rememberOptions.value = true;
    localStorage.removeItem(STORAGE_KEY);
    return true;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return false;
  }
}

function initializeProfile(restored: boolean) {
  const profile = currentProfile.value;
  if (!profile) return;
  if (!restored) normalizeOptions(profile.defaultOptions || {});
  if (!Array.isArray(options.basePackages)) options.basePackages = [...basePackages.value];
  for (const required of requiredPackageSet.value) {
    if (!options.basePackages.includes(required)) options.basePackages.push(required);
  }
  options.basePackages = options.basePackages.filter((name) => basePackageSet.value.has(name));
  options.selectedPackages = options.selectedPackages.filter((name) => (
    !allPresetManagedPackages.value.has(name) && !basePackageSet.value.has(name)
  ));
  for (const [primary, members] of Object.entries(presets.value.packageGroups ?? {})) {
    if (!options.selectedPackages.includes(primary)) continue;
    for (const member of members) {
      if (!options.selectedPackages.includes(member)) options.selectedPackages.push(member);
    }
  }
  if (!options.feeds.length) options.feeds = cloneFeeds(profile.feeds);
}

function savedConfigPayload() {
  return {
    options: JSON.parse(JSON.stringify(options)) as BuildOptions,
    jobs: jobs.value,
    clean: clean.value
  };
}

async function loadSavedOptions(): Promise<boolean> {
  const saved = await api<SavedConfigResponse>(`/api/saved-config/${selectedProfile.value}`);
  if (!saved.saved || !saved.options) {
    rememberOptions.value = false;
    return false;
  }
  normalizeOptions(saved.options);
  jobs.value = saved.jobs;
  clean.value = saved.clean;
  rememberOptions.value = true;
  localStorage.removeItem(STORAGE_KEY);
  return true;
}

async function persistOptions(profile = selectedProfile.value, showError = false) {
  if (!rememberOptions.value) return;
  try {
    await api<{ saved: boolean }>(`/api/saved-config/${profile}`, {
      method: 'PUT',
      body: JSON.stringify(savedConfigPayload())
    });
  } catch (error) {
    if (showError) message.error(error instanceof Error ? error.message : '配置保存失败');
  }
}

function scheduleOptionsSave() {
  if (!persistenceReady.value || !rememberOptions.value) return;
  if (persistenceTimer !== null) window.clearTimeout(persistenceTimer);
  persistenceTimer = window.setTimeout(() => {
    persistenceTimer = null;
    void persistOptions();
  }, 500);
}

async function removeSavedOptions(profile = selectedProfile.value) {
  await api<{ saved: boolean }>(`/api/saved-config/${profile}`, { method: 'DELETE' });
}

async function loadProfiles() {
  const data = await api<{ profiles: Profile[] }>('/api/profiles');
  profiles.value = data.profiles;
  if (!profiles.value.some((profile) => profile.name === selectedProfile.value) && profiles.value[0]) selectedProfile.value = profiles.value[0].name;
}
async function loadStatus() { status.value = await api<BuildStatus>('/api/status'); logs.value = status.value.logs; }
async function loadArtifacts() { artifacts.value = (await api<{ artifacts: Artifact[] }>(`/api/artifacts/${selectedProfile.value}`)).artifacts; }
async function loadPackageCatalog() {
  catalog.value = await api<PackageCatalog>(`/api/package-catalog/${selectedProfile.value}`);
  if (!packageCategoryOptions.value.some((item) => item.value === packageCategory.value)) packageCategory.value = 'all';
  if (!packageSourceOptions.value.some((item) => item.value === packageSource.value)) packageSource.value = 'all';
}
async function syncCatalog() {
  syncingCatalog.value = true;
  try {
    const feeds = effectiveFeeds();
    validateFeeds(feeds);
    catalog.value = await api<PackageCatalog>(`/api/package-catalog/${selectedProfile.value}/refresh`, { method: 'POST', body: JSON.stringify({ feeds }) });
    await persistOptions(selectedProfile.value, true);
    message.success(`软件库已同步，共 ${catalog.value.total.toLocaleString()} 项`);
  } catch (error) {
    message.error(error instanceof Error ? error.message : '软件库同步失败');
  } finally {
    syncingCatalog.value = false;
  }
}

function validateFeeds(feeds: FeedSource[]) {
  const names = new Set<string>();
  const urlPattern = /^https:\/\/[a-zA-Z0-9.-]+(?::[0-9]{1,5})?\/[a-zA-Z0-9._~%+/@:-]+$/;
  const branchPattern = /^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$/;
  for (const feed of feeds) {
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$/.test(feed.name) || names.has(feed.name)) throw new Error(`软件源名称无效或重复: ${feed.name}`);
    if (feed.enabled && (!urlPattern.test(feed.url) || feed.url.includes('/../') || feed.url.endsWith('/..'))) throw new Error(`软件源 ${feed.name} 需要有效的 HTTPS Git 地址`);
    if (!branchPattern.test(feed.branch) || feed.branch.startsWith('-') || feed.branch.includes('..')) throw new Error(`软件源 ${feed.name} 的分支名称无效`);
    names.add(feed.name);
  }
}

async function startBuild() {
  try {
    normalizeAuthorLink();
    const feeds = effectiveFeeds();
    validateFeeds(feeds);
    await persistOptions(selectedProfile.value, true);
    status.value = await api<BuildStatus>('/api/build', {
      method: 'POST',
      body: JSON.stringify({ profile: selectedProfile.value, jobs: jobs.value, clean: clean.value, options: { ...JSON.parse(JSON.stringify(options)), feeds } })
    });
    logs.value = status.value.logs;
    activeTab.value = 'outputs';
    outputSections.value = ['logs'];
    message.success('构建已开始');
  } catch (error) {
    message.error(error instanceof Error ? error.message : '启动失败');
  }
}
async function stopBuild() {
  try { status.value = await api<BuildStatus>('/api/stop', { method: 'POST' }); message.warning('已发送停止请求'); }
  catch (error) { message.error(error instanceof Error ? error.message : '停止失败'); }
}

let logSource: EventSource | null = null;
let refreshTimer: number | null = null;
let persistenceTimer: number | null = null;
function connectLogs() {
  logSource = new EventSource('/api/logs/stream');
  const seen = new Set(logs.value.map((line) => `${line.ts}:${line.text}`));
  logSource.onmessage = (event) => {
    const line = JSON.parse(event.data) as LogLine;
    const key = `${line.ts}:${line.text}`;
    if (seen.has(key)) return;
    seen.add(key);
    logs.value.push(line);
    if (logs.value.length > 1000) logs.value.splice(0, logs.value.length - 1000);
  };
}

watch(logs, async () => {
  await nextTick();
  if (logRef.value && outputSections.value.includes('logs')) logRef.value.scrollTop = logRef.value.scrollHeight;
}, { deep: true });
watch(rememberOptions, async (enabled) => {
  if (!persistenceReady.value) return;
  if (persistenceTimer !== null) {
    window.clearTimeout(persistenceTimer);
    persistenceTimer = null;
  }
  try {
    if (enabled) await persistOptions(selectedProfile.value, true);
    else await removeSavedOptions();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '本地配置更新失败');
  }
});
watch(options, scheduleOptionsSave, { deep: true });
watch([jobs, clean], scheduleOptionsSave);
watch(() => options.webServer, () => { if (!selectedWebServer.value?.supportsHttps) options.httpsAdmin = false; });
watch(() => options.runtimeMirror, (mirror) => { if (mirror !== 'custom') options.customMirrorUrl = ''; });
watch(() => options.firewallBackend, () => {
  const removed = options.proxyPresets.filter((id) => {
    const proxy = proxyPresets.value.find((item) => item.id === id);
    return proxy && !proxyCompatible(proxy);
  });
  if (removed.length) {
    options.proxyPresets = options.proxyPresets.filter((id) => !removed.includes(id));
    message.warning('已取消与当前防火墙后端不兼容的代理预设');
  }
});
watch(selectedProfile, async (_profile, previousProfile) => {
  if (!persistenceReady.value) return;
  mirrorChecks.value = {};
  if (persistenceTimer !== null) {
    window.clearTimeout(persistenceTimer);
    persistenceTimer = null;
  }
  if (rememberOptions.value) await persistOptions(previousProfile);
  persistenceReady.value = false;
  const restored = await loadSavedOptions();
  initializeProfile(restored);
  persistenceReady.value = true;
  await Promise.all([loadArtifacts(), loadPackageCatalog()]);
});

onMounted(async () => {
  try {
    await loadProfiles();
    let restored = await loadSavedOptions();
    const migrated = !restored && loadLegacyRememberedOptions();
    restored ||= migrated;
    initializeProfile(restored);
    await Promise.all([loadStatus(), loadArtifacts(), loadPackageCatalog()]);
    persistenceReady.value = true;
    if (migrated) await persistOptions(selectedProfile.value, true);
    connectLogs();
    refreshTimer = window.setInterval(() => { void Promise.allSettled([loadStatus(), loadArtifacts()]); }, 5000);
  } catch (error) {
    message.error(error instanceof Error ? error.message : '初始化失败');
  }
});
onUnmounted(() => {
  logSource?.close();
  if (refreshTimer !== null) window.clearInterval(refreshTimer);
  if (persistenceTimer !== null) window.clearTimeout(persistenceTimer);
});
</script>
