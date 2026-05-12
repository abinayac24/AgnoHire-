from fastapi import APIRouter


router = APIRouter(tags=["metadata"])


@router.get("/metadata/domains")
def get_domains():
    return {
        "domains": [
            "Java",
            "Python",
            "Web Development",
            "AI / Machine Learning",
            "Spring Boot",
            "React",
            "DevOps",
            "Data Structures",
            "System Design",
        ]
    }
