import {createApi} from '../lib/api.mjs';
const handle = createApi();
export default request => handle(request, 'analyze');
export const config = {
  path: '/api/analyze',
  method: 'POST',
  rateLimit: {windowSize: 60, windowLimit: 2, aggregateBy: ['domain']},
};
