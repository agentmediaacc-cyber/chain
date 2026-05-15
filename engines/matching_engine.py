def calculate_profile_score(current, target):
    score = 45

    if current.get("country_origin") and current.get("country_origin") == target.get("country_origin"):
        score += 10

    if current.get("current_location") and current.get("current_location") == target.get("current_location"):
        score += 15

    if current.get("relationship_goal") and current.get("relationship_goal") == target.get("relationship_goal"):
        score += 15

    shared = set(current.get("interests") or []).intersection(set(target.get("interests") or []))
    score += min(len(shared) * 5, 20)

    if target.get("is_verified"):
        score += 5

    if target.get("is_creator"):
        score += 3

    return min(score, 99)


def rank_profiles(current, profiles):
    ranked = []
    for profile in profiles:
        profile["match_score"] = calculate_profile_score(current, profile)
        ranked.append(profile)
    return sorted(ranked, key=lambda x: x.get("match_score", 0), reverse=True)
