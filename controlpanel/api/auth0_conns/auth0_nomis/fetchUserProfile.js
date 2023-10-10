function fetchUserProfile(accessToken, context, callback) {
  // The email is only for auth0 usage purpose, not the actual email of login user
  const profile = {
    sub: context.sub,
    user_id: context.user_id,
    auth_source: context.auth_source,
    nickname: context.name,
    name: context.name,
    username: context.user_name,
    _deliusAccessToken: accessToken,
    _accessToken: accessToken,
    email: context.user_name + "+" + context.user_id + "@" + context.auth_source,
  };
  callback(null, profile);
}
