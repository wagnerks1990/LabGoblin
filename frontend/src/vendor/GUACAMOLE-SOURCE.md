# Apache Guacamole JavaScript client

Version: 1.6.0, upstream tag `1.6.0` in
https://github.com/apache/guacamole-client.

`guacamole-1.6.0.js` concatenates all 35 JavaScript modules from
`guacamole-common-js/src/main/webapp/modules/` in filename order. The only
LabGoblin addition is `export default Guacamole;` so Vite can bundle the
upstream implementation as an ES module. No upstream module behavior is
modified. Original file license headers are retained; the repository LICENSE
and NOTICE are included alongside the source. Vite bundles/minifies this code
with the application; no runtime CDN or separate site is used.

To update, fetch the modules from a reviewed Apache release, preserve license
and notice, record new hashes, and update the guacd image to the matching
version. Run protocol integration tests and validate real guest sessions.
