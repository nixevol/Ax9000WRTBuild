include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-frpc
PKG_VERSION:=2.0
PKG_RELEASE:=7
PKG_PO_VERSION:=$(PKG_VERSION)-r$(PKG_RELEASE)
PKG_LICENSE:=Apache-2.0
PKG_MAINTAINER:=local

LUCI_TITLE:=frp Client
LUCI_BASENAME:=frpc
LUCI_DEPENDS:=+frpc +cgi-io
LUCI_PKGARCH:=all

define Build/Prepare/luci-app-frpc
	$(FIND) $(PKG_BUILD_DIR)/root -type f -exec chmod 0644 {} +
	chmod 0755 \
		$(PKG_BUILD_DIR)/root/etc/uci-defaults/99-luci-app-frpc \
		$(PKG_BUILD_DIR)/root/usr/libexec/frpc-launcher \
		$(PKG_BUILD_DIR)/root/usr/libexec/rpcd/frpc-manager
endef

define Package/luci-app-frpc/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] && exit 0
if grep -q '^PROG=/usr/libexec/frpc-launcher$$' /etc/init.d/frpc 2>/dev/null; then
	sed -i 's#^PROG=/usr/libexec/frpc-launcher$$#PROG=/usr/bin/$$NAME#' /etc/init.d/frpc
fi
exit 0
endef

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
