
# Extracting user's info 
async def extract_user_info_from_metadata(metadata: dict) -> tuple[str, dict]:
    """
    Extract user information from job metadata
    """
    user_identifier = None
    user_metadata = {}
    
    # Try to extract user info from various sources
    if "caller_number" in metadata:
        user_identifier = f"phone_{metadata['caller_number']}"
        user_metadata["phone_number"] = metadata["caller_number"]
    
    if "caller_id" in metadata:
        user_identifier = metadata["caller_id"]
        
    if "user_id" in metadata:
        user_identifier = metadata["user_id"]
    
    # Extract other user-related metadata
    user_fields = ["caller_name", "location", "timezone", "language_preference", "customer_id"]
    for field in user_fields:
        if field in metadata:
            user_metadata[field] = metadata[field]
    
    return user_identifier, user_metadata