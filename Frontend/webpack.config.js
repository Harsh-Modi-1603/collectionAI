const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  entry: './src/index.js', // Your main JS file
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'main.js',
    clean: true, // clean old files on build
  },
  mode: 'development',
  devServer: {
    static: {
      directory: path.join(__dirname, 'public'), // Serve index.html from public
    },
    port: 8080,
    hot: true,
    open: true,
  },
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/, // Transpile JS and JSX files
        exclude: /node_modules/,
        use: 'babel-loader',
      },
      {
        test: /\.css$/i, // Handle CSS imports
        use: ['style-loader', 'css-loader'],
      },
      {
        test: /\.(png|jpe?g|gif|svg)$/i, // Handle images
        type: 'asset/resource',
      },
    ],
  },
  resolve: {
    extensions: ['.js', '.jsx'], // Import without extension
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: './public/index.html', // HTML template
    }),
  ],
};
