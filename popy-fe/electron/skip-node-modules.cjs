/** The packaged window loads a Vite bundle. Django and MySQL ship as extra resources. */
module.exports = async function beforeBuild() {
  return false;
};
