const path = require('path');

module.exports = {
  entry: {
    'main': './src/index.js'
  },
  output: {
    filename: '[name].js',
    path: path.resolve(__dirname, 'dist'),
    clean: true,
    hashFunction: 'xxhash64'
  },
  module: {
    rules: [
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader'],
      },
      {
        test: /\.(gif|jpe?g|png|svg|webp)$/i,
        use: ['file-loader'],
      },
    ],
  },
};
