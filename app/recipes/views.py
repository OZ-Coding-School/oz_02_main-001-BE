from django.shortcuts import render
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from .models import Recipe, Recipe_ingredient, Recipe_step
from .serializers import RecipeSerializer, Recipe_stepSerializer
from ingredients.models import Ingredient
from bookmarks.models import Bookmark
from likes.models import Like
from comments.models import Comment
from users.models import User


class RecipeRecommendView(APIView):
    def post(self, request):
        # 요청에서 사용자가 입력한 재료 ID 목록 가져오기
        user_id = request.user.id
        if not user_id:
            return Response({"status": 400, "message": "사용자 인증이 필요합니다."}, status=400)
        
        data = request.data
        ingredient_ids = data.get("ingredients", [])

        # 입력된 재료 ID로 실제 재료 객체 조회
        ingredients = Ingredient.objects.filter(id__in=ingredient_ids)
        # 조회된 재료 객체의 이름 목록 생성
        ingredient_names = [ingredient.name for ingredient in ingredients]

        # 입력된 재료를 포함하는 레시피 목록 조회
        recipes = Recipe.objects.filter(
            recipe_ingredient__ingredient__in=ingredients
        ).distinct()

        # 레시피 정보를 담을 리스트 초기화
        recipe_data = []
        for recipe in recipes:
            # 레시피 작성자 정보 가져오기
            user = User.objects.get(id=recipe.user_id)
            # 레시피 좋아요 수 가져오기
            like = Like.objects.filter(recipe_id=recipe.id).count()
            # 레시피 북마크 수 가져오기
            bookmark = Bookmark.objects.filter(recipe_id=recipe.id).count()

            # 사용자의 좋아요 및 북마크 상태 확인
            like_status = (
                Like.objects.filter(recipe_id=recipe.id, user_id=user_id)
                .values_list("id", flat=True)
                .first()
            )
            if like_status:
                like_status = 1
            else:
                like_status = -1

            bookmark_status = (
                Bookmark.objects.filter(recipe_id=recipe.id, user_id=user_id)
                .values_list("id", flat=True)
                .first()
            )
            if bookmark_status:
                bookmark_status = 1
            else:
                bookmark_status = -1

            # 레시피에 포함된 재료 이름 목록 생성
            recipe_ingredients = [
                item.ingredient.name for item in recipe.recipe_ingredient.all()
            ]

            # 입력된 재료 중 레시피에 포함된 재료와 포함되지 않은 재료 구분
            include_ingredients = [
                name for name in ingredient_names if name in recipe_ingredients
            ]
            not_include_ingredients = [
                name for name in recipe_ingredients if name not in include_ingredients
            ]

            recipe_info = {
                "recipe_id": recipe.id,
                "nickname": user.nickname,
                "include_ingredients": include_ingredients,
                "not_include_ingredients": not_include_ingredients,
                "title": recipe.title,
                "likes": like,
                "bookmark": bookmark,
                "like_status": like_status,
                "bookmark_status": bookmark_status,
            }
            recipe_data.append(recipe_info)

        response_data = {
            "status": 200,
            "message": "조회 성공",
            "data": {"ingredients": ingredient_names, "recipes": recipe_data},
        }

        # 응답 반환
        return Response(response_data)


from .models import Temp_recipe, Temp_step, Unit
from .utils import create_file

class CreateTempImage(APIView):
    def post(self, request):
        user = request.user

        if not user.is_authenticated:
            return Response({"status": "400", "message": "토큰이 없습니다"}, 400)

        actions = request.data.get("action")
        if actions == "write":
            if "image" in request.data:
                image_data = request.data["image"]
                type_data = request.data["type"]
                order =request.data.get("order")

                if type_data not in ["main", "step"]:
                    return Response(
                        {"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST
                    )

                format, imgstr = image_data.split(";base64,")
                ext = format.split("/")[-1]

                image_file = create_file(type_data, ext, imgstr, order)

                # Temp_recipe 객체를 먼저 저장하여 ID를 할당
                if type_data == "main":
                    temp_recipe, _ = Temp_recipe.objects.get_or_create(
                        user_id=user.id, status=1
                    )  # 객체 생성 및 저장
                    temp_recipe.main_image = image_file  # 이미지 파일 할당
                    temp_recipe.save()  # 다시 저장하여 파일을 저장

                    data = {
                        "status": 201,
                        "message": "임시 레시피 이미지 저장 성공",
                        "data": {"id": temp_recipe.id, "image": temp_recipe.main_image.url},
                    }
                    return Response(data, status=status.HTTP_201_CREATED)
                else:
                    temp_recipe = Temp_recipe.objects.filter(
                        user_id=user.id, status=1
                    ).last()

                    if not temp_recipe:
                        return Response(
                            {"error": "유효한 Temp_recipe를 찾을 수 없습니다."},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    # Temp_step 객체를 먼저 생성하여 ID를 할당하고 Temp_recipe와 연결
                    temp_step, _ = Temp_step.objects.get_or_create(
                        recipe=temp_recipe, order=order
                    )
                    temp_step.image = image_file
                    temp_step.save()

                    data = {
                        "status": 201,
                        "message": "임시 레시피 이미지 저장 성공",
                        "data": {"id": temp_step.id, "image": temp_step.image.url},
                    }
                    return Response(data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"error": "No image data provided"}, status=status.HTTP_400_BAD_REQUEST
                )
                   
import os
from .utils import copy_file
from config.settings import BUCKET_PATH
class CreateRecipe(APIView):
    def post(self, request):
        user_id = request.user.id
        if not user_id:
            return Response({"status": 400, "message": "사용자 인증이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            temp_recipe = Temp_recipe.objects.filter(user_id=user_id, status=1).first()

            if not temp_recipe:
                return Response({"error": "Temporary recipe not found."}, status=status.HTTP_404_NOT_FOUND)

            # 요청 데이터를 복사하여 수정 가능하게 만듭니다.
            data = request.data.copy()

            recipe_ingredients_data = data.pop('recipe_ingredients', [])
            steps_data = data.pop('steps', [])

            recipe = Recipe.objects.create(user_id=user_id, **data)
            temp_recipe.recipe = recipe
            temp_recipe.save()

            if temp_recipe.main_image:
                main_image_source = temp_recipe.main_image.name
                main_image_dest = f'{BUCKET_PATH}recipe/{recipe.id}/{os.path.basename(main_image_source)}'
                print(main_image_dest)
                copy_file(main_image_source, main_image_dest)

                recipe.main_image = main_image_dest
                recipe.save()

            temp_steps = Temp_step.objects.filter(recipe=temp_recipe).order_by('order')
            count = 0

            for i, step_text in enumerate(steps_data, 1):
                temp_image = None
                if temp_steps and count < len(temp_steps):
                    if i == temp_steps[count].order:
                        temp_image = temp_steps[count].image
                        count += 1

                step_data = {'recipe': recipe.id, 'step': step_text}
                step_serializer = Recipe_stepSerializer(data=step_data)

                if step_serializer.is_valid():
                    recipe_step = step_serializer.save()
                    if temp_image:
                        temp_image_source = temp_image.name
                        temp_image_dest = f'{BUCKET_PATH}recipe/{recipe.id}/{os.path.basename(temp_image_source)}'
                        copy_file(temp_image_source, temp_image_dest)

                        recipe_step.image = temp_image_dest
                        recipe_step.save()
                else:
                    print("Errors:", step_serializer.errors)

            # temp_recipe 상태 업데이트
            temp_recipe.status = 0
            temp_recipe.save()

            response_data = {
                "status": 201,
                "message": "레시피 작성 성공",
                "data": {"id": recipe.id},
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class RecipeDetailDeleteView(APIView):
    def get(self, request, id):
        try:
            recipe = Recipe.objects.get(pk=id)
            bookmarks_count = Bookmark.objects.filter(recipe_id=id).count()
            likes_count = Like.objects.filter(recipe_id=id).count()

            # 테스트용 user_id 하드코딩
            user_id = request.user.id

            like_status = (
                Like.objects.filter(recipe_id=id, user_id=user_id)
                .values_list("id", flat=True)
                .first()
            )
            if like_status:
                like_status = 1
            else:
                like_status = -1

            bookmark_status = (
                Bookmark.objects.filter(recipe_id=id, user_id=user_id)
                .values_list("id", flat=True)
                .first()
            )
            if bookmark_status:
                bookmark_status = 1
            else:
                bookmark_status = -1

            # is_staff 값이 True이거나 user_id가 본인이면 canUpdate를 1로 설정
            user = User.objects.get(id=user_id)
            if user.is_staff or user.id == recipe.user.id:
                can_update = 1
            else:
                can_update = 0

            ingredients = Recipe_ingredient.objects.filter(recipe_id=id).order_by('id')
            steps = Recipe_step.objects.filter(recipe_id=id).order_by('id')
            comments = (
                Comment.objects.filter(recipe_id=id)
                .select_related("user")
                .values(
                    "id",
                    "user__id",
                    "user__nickname",
                    "updated_at",
                    "comment",
                    "user__image",
                )
            )

            # 각 댓글의 can_update 값 설정
            comment_data = []
            for comment in comments:
                if user.is_staff or comment["user__id"] == user_id:
                    comment_can_update = 1
                else:
                    comment_can_update = 0
                comment_data.append(
                    {
                        "id": comment["id"],
                        "user_id": comment["user__id"],
                        "user_nickname": comment["user__nickname"],
                        "profile_image": comment["user__image"],
                        "updated_at": comment["updated_at"],
                        "comment": comment["comment"],
                        "can_update": comment_can_update,
                    }
                )

            serializer = RecipeSerializer(recipe)
            data = {
                "status": status.HTTP_200_OK,
                "message": "레시피 조회 성공",
                "data": {
                    "can_update": can_update,
                    **serializer.data,
                    "like": likes_count,
                    "like_status": like_status,
                    "book": bookmarks_count,
                    "book_status": bookmark_status,
                    "user": {
                        "id": recipe.user.id,
                        "nickname": recipe.user.nickname,
                        "profile_image": recipe.user.image,
                        "date": recipe.updated_at,
                    },
                    
                    "ingredients": [
                        {
                            "id": ingredient.id,
                            "name": ingredient.ingredient.name,
                            "quantity": ingredient.quantity,
                            "unit": ingredient.unit.unit,
                        }
                        for ingredient in ingredients
                    ],
                    "steps": [
                        {"step": step.step, "image": step.image.url if step.image else ""} for step in steps
                    ],
                    "comments": comment_data,
                },
            }
            return Response(data)
        except Recipe.DoesNotExist:
            return Response(
                {
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": f"ID {id}에 해당하는 레시피를 찾을 수 없습니다.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    def get_object(self, id):
        try:
            return Recipe.objects.get(pk=id)
        except Recipe.DoesNotExist:
            raise NotFound(f"ID {id}에 해당하는 레시피를 찾을 수 없습니다.")

    def delete(self, request, id):
        recipe = self.get_object(id)
        recipe.delete()
        data = {"status": 200, "message": "레시피 삭제 성공"}
        return Response(data, status=status.HTTP_200_OK)


class RecipeCategoryListView(APIView):
    def get_category_name(self, category):
        category_mapping = {
            "daily": "1",
            "healthy": "2",
            "midnight": "3",
            "desert": "4",
        }
        return category_mapping.get(category, None)

    def get(self, request, category=None):
        user_id = request.user.id  # 현재 사용자의 ID 가져오기
        category_name = self.get_category_name(category)

        if category == "like":
            # 사용자가 좋아요를 누른 레시피만 필터링
            recipes = Recipe.objects.filter(like__user_id=user_id)
        elif category == "book":
            # 사용자가 북마크한 레시피만 필터링
            recipes = Recipe.objects.filter(bookmark__user_id=user_id)
        elif category_name:
            # 특정 카테고리의 레시피만 필터링
            recipes = Recipe.objects.filter(category=category_name)
        else:
            return Response(
                {
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "유효한 카테고리가 아닙니다.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        recipe_data = []
        for recipe in recipes:
            user = User.objects.get(id=recipe.user_id)
            like = Like.objects.filter(recipe_id=recipe.id, user_id=user_id).first()
            book = Bookmark.objects.filter(recipe_id=recipe.id, user_id=user_id).first()

            like_status = 1 if like else -1
            book_status = 1 if book else -1

            recipe_info = {
                "id": recipe.id,
                "user": user.nickname,
                "title": recipe.title,
                "main_image": recipe.main_image.url,
                "like": Like.objects.filter(recipe_id=recipe.id).count(),
                "like_status": like_status,
                "book": Bookmark.objects.filter(recipe_id=recipe.id).count(),
                "book_status": book_status,
            }
            recipe_data.append(recipe_info)

        response_data = {
            "status": 200,
            "message": (
                "카테고리 레시피 조회 성공"
                if category_name
                else "좋아요 및 북마크 레시피 조회 성공"
            ),
            "data": recipe_data,
        }

        return Response(response_data)


class RecipeSearchKeywordView(APIView):
    def get(self, request, keyword):
        user_id = request.user.id
        if not keyword:
            return Response({"message": "검색어를 입력해 주세요."}, status=400)

        recipes = Recipe.objects.filter(
            Q(title__icontains=keyword)
            | Q(recipe_ingredient__ingredient__name__icontains=keyword)
            | Q(recipe_step__step__icontains=keyword)
        ).distinct()

        if not recipes:
            return Response({"message": "해당되는 레시피가 없습니다."}, status=404)

        recipe_data = []
        for recipe in recipes:
            user = User.objects.get(id=recipe.user_id)
            like = Like.objects.filter(recipe_id=recipe.id, user_id=user_id).first()
            book = Bookmark.objects.filter(recipe_id=recipe.id, user_id=user_id).first()

            like_status = 1 if like else -1
            book_status = 1 if book else -1

            recipe_info = {
                "id": recipe.id,
                "user": user.nickname,
                "title": recipe.title,
                "main_image": recipe.main_image.url,
                "like": Like.objects.filter(recipe_id=recipe.id).count(),
                "like_status": like_status,
                "book": Bookmark.objects.filter(recipe_id=recipe.id).count(),
                "book_status": book_status,
            }
            recipe_data.append(recipe_info)

        response_data = {
            "status": 200,
            "message": "레시피 조회 성공",
            "data": recipe_data,
        }
        return Response(response_data, status=status.HTTP_200_OK)

