include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-ax900-hardware
PKG_VERSION:=1.0.0
PKG_RELEASE:=9
PKG_LICENSE:=PolyForm-Noncommercial-1.0.0
PKGARCH:=all
PKG_BUILD_DEPENDS:=luci-base/host

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-ax900-hardware
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=OpenWRT AX9000 fan and LED control
  DEPENDS:=+luci-base +rpcd +kmod-hwmon-emc2305
endef

define Package/luci-i18n-ax900-hardware-zh-cn
  SECTION:=luci
  CATEGORY:=LuCI
  TITLE:=OpenWRT AX9000 hardware control - Simplified Chinese translation
  DEPENDS:=+luci-app-ax900-hardware
  DEFAULT:=LUCI_LANG_zh_Hans||(ALL&&m)
  PKGARCH:=all
endef

define Package/luci-app-ax900-hardware/conffiles
/etc/config/ax900-hardware
endef

define Build/Compile
endef

define Package/luci-app-ax900-hardware/install
	$(INSTALL_DIR) $(1)/etc/config $(1)/etc/init.d $(1)/etc/uci-defaults
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/usr/share/luci/menu.d
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/ax900-hardware
	$(INSTALL_DIR) $(1)/www/luci-static/resources/ax900-hardware/icons
	$(INSTALL_CONF) ./files/etc/config/ax900-hardware $(1)/etc/config/ax900-hardware
	$(INSTALL_BIN) ./files/etc/init.d/ax900-hardware $(1)/etc/init.d/ax900-hardware
	$(INSTALL_BIN) ./files/etc/init.d/ax900-led $(1)/etc/init.d/ax900-led
	$(INSTALL_BIN) ./files/etc/uci-defaults/99-ax900-hardware $(1)/etc/uci-defaults/99-ax900-hardware
	$(INSTALL_BIN) ./files/usr/sbin/ax900-hardware-control $(1)/usr/sbin/ax900-hardware-control
	$(INSTALL_BIN) ./files/usr/sbin/ax900-led-control $(1)/usr/sbin/ax900-led-control
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/ax900-hardware $(1)/usr/libexec/rpcd/ax900-hardware
	$(INSTALL_DATA) ./files/usr/share/luci/menu.d/luci-app-ax900-hardware.json $(1)/usr/share/luci/menu.d/luci-app-ax900-hardware.json
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/luci-app-ax900-hardware.json $(1)/usr/share/rpcd/acl.d/luci-app-ax900-hardware.json
	$(INSTALL_DATA) ./files/www/luci-static/resources/view/ax900-hardware/settings.js $(1)/www/luci-static/resources/view/ax900-hardware/settings.js
	$(INSTALL_DATA) ./files/www/luci-static/resources/ax900-hardware/icons/*.svg $(1)/www/luci-static/resources/ax900-hardware/icons/
endef

define Package/luci-i18n-ax900-hardware-zh-cn/install
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/i18n
	po2lmo ./po/zh_Hans/ax900-hardware.po $(1)/usr/lib/lua/luci/i18n/ax900-hardware.zh-cn.lmo
endef

$(eval $(call BuildPackage,luci-app-ax900-hardware))
$(eval $(call BuildPackage,luci-i18n-ax900-hardware-zh-cn))
