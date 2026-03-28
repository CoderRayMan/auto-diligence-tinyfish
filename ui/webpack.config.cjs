const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");

module.exports = (env, argv) => {
  const isDev = argv.mode !== "production";

  return {
    entry: "./src/main.tsx",
    output: {
      path: path.resolve(__dirname, "dist"),
      filename: "bundle.[contenthash].js",
      publicPath: "/",
      clean: true,
    },
    resolve: {
      extensions: [".tsx", ".ts", ".jsx", ".js"],
    },
    module: {
      rules: [
        {
          test: /\.[jt]sx?$/,
          exclude: /node_modules/,
          use: {
            loader: "babel-loader",
            options: {
              presets: [
                ["@babel/preset-env", { targets: "defaults", modules: false }],
                ["@babel/preset-react", { runtime: "automatic" }],
                ["@babel/preset-typescript", { allExtensions: true, isTSX: true }],
              ],
            },
          },
        },
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        template: "./index.html",
        inject: "body",
      }),
    ],
    devServer: {
      port: 5174,
      hot: true,
      compress: false,        // SSE: gzip buffering breaks real-time event streams
      historyApiFallback: true,
      proxy: [
        {
          context: ["/api"],
          target: "http://localhost:8000",
          changeOrigin: true,
          // SSE: ensure no response buffering through the proxy
          selfHandleResponse: false,
          onProxyReq: (proxyReq) => {
            proxyReq.setHeader("Accept-Encoding", "identity");
          },
        },
      ],
    },
    devtool: isDev ? "cheap-module-source-map" : false,
    mode: isDev ? "development" : "production",
    performance: { hints: false },
  };
};
